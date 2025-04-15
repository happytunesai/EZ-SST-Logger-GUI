# -*- coding: utf-8 -*-
"""
Funktionen für WebSocket-Server (externe Steuerung) und Client (Streamer.bot).
Streamer.bot Client Logik vereinfacht für bessere Kompatibilität.
"""
import asyncio
import threading
import queue
import json

# Importiere abhängige Bibliotheken mit Fehlerbehandlung
try:
    import websockets
except ImportError:
    websockets = None

# Importiere lokale Module/Objekte
from lib.logger_setup import logger
from lib.constants import WEBSOCKET_PORT

# --- WebSocket Server (für externe Steuerung) ---
# (Keine Änderungen hier)
async def websocket_handler(websocket, path, gui_q):
    client_addr = websocket.remote_address
    logger.info(f"WebSocket Client verbunden: {client_addr}")
    try:
        async for message in websocket:
            logger.info(f"WebSocket Nachricht empfangen von {client_addr}: {message}")
            if isinstance(message, str):
                command = message.strip().upper()
                if command == "TOGGLE_RECORD":
                    logger.info("WebSocket: Sende Start/Stop Signal an GUI...")
                    gui_q.put(("toggle_recording_external", None))
                    await websocket.send("OK: TOGGLE_RECORD empfangen und weitergeleitet.")
                elif command == "PING":
                     await websocket.send("PONG")
                else:
                    logger.warning(f"WebSocket: Unbekannter Befehl '{message}' von {client_addr}")
                    await websocket.send(f"FEHLER: Unbekannter Befehl '{message}'")
            else:
                logger.warning(f"WebSocket: Empfangene Nachricht von {client_addr} ist kein Text.")
                await websocket.send("FEHLER: Nur Textnachrichten werden akzeptiert.")
    except websockets.exceptions.ConnectionClosedOK:
        logger.info(f"WebSocket Client getrennt (OK): {client_addr}")
    except websockets.exceptions.ConnectionClosedError as ws_err:
        logger.warning(f"WebSocket Client getrennt (Error): {client_addr} - {ws_err}")
    except Exception as e:
        logger.exception(f"WebSocket Fehler im Handler für Client {client_addr}")
    finally:
        logger.info(f"WebSocket Verbindung geschlossen für: {client_addr}")

async def run_websocket_server(stop_event, port, gui_q):
    host = "localhost"
    if not websockets:
        logger.error("WebSocket-Bibliothek nicht verfügbar. Server kann nicht gestartet werden.")
        gui_q.put(("error", "WebSocket Lib fehlt!"))
        return
    server_instance = None
    try:
        handler_with_queue = lambda ws, path: websocket_handler(ws, path, gui_q)
        server_instance = await websockets.serve(handler_with_queue, host, port)
        logger.info(f"WebSocket Server gestartet auf ws://{host}:{port}")
        gui_q.put(("status", f"WebSocket Server läuft auf Port {port}"))
        await stop_event.wait()
        logger.info("WebSocket Server wird gestoppt (Stop-Event empfangen)...")
    except OSError as e:
        if "address already in use" in str(e).lower():
             logger.error(f"FEHLER beim Starten des WebSocket Servers: Port {port} ist bereits belegt.")
             gui_q.put(("error", f"WebSocket Port {port} belegt!"))
        else:
             logger.error(f"FEHLER beim Starten des WebSocket Servers auf Port {port}: {e}")
             gui_q.put(("error", f"WebSocket Port {port} Fehler: {e}"))
    except Exception as e:
        logger.exception("Unerwarteter FEHLER im WebSocket Server Task")
        gui_q.put(("error", f"WebSocket Server Fehler: {e}"))
    finally:
        if server_instance:
            server_instance.close()
            await server_instance.wait_closed()
            logger.info("WebSocket Server Instanz geschlossen.")
        logger.info("WebSocket Server Task beendet.")
        gui_q.put(("status", "WebSocket Server gestoppt."))

def start_websocket_server_thread(port, gui_q):
    if not isinstance(port, int) or not 1 <= port <= 65535:
        logger.error(f"Ungültiger WebSocket Port angegeben: {port}. Server nicht gestartet.")
        gui_q.put(("error", f"Ungültiger WS Port: {port}"))
        return None, None
    loop = asyncio.new_event_loop()
    stop_event = asyncio.Event()
    def run_loop():
        asyncio.set_event_loop(loop)
        setattr(stop_event, '_custom_loop_ref', loop)
        try:
            loop.run_until_complete(run_websocket_server(stop_event, port, gui_q))
        except Exception as e:
             logger.exception("Fehler während der Ausführung des WebSocket Server Loops im Thread")
        finally:
            logger.info("WebSocket Server Loop im Thread beendet. Räume auf...")
            try:
                tasks = asyncio.all_tasks(loop=loop)
                for task in tasks:
                    if not task.done(): task.cancel()
                if loop.is_running():
                    loop.run_until_complete(asyncio.sleep(0.1, loop=loop))
            except RuntimeError as e:
                 if "cannot schedule new futures after shutdown" in str(e): logger.debug("Loop wurde bereits heruntergefahren.")
                 else: logger.error(f"Laufzeitfehler beim Aufräumen der asyncio Tasks im WS Server Thread: {e}")
            except Exception as e_cancel: logger.error(f"Fehler beim Aufräumen der asyncio Tasks im WS Server Thread: {e_cancel}")
            finally:
                 if not loop.is_closed():
                      if loop.is_running(): loop.stop()
                      loop.close()
                      logger.info("WebSocket Server Event Loop geschlossen.")
                 else: logger.info("WebSocket Server Event Loop war bereits geschlossen.")
                 logger.info("WebSocket Server Thread vollständig beendet.")
    logger.info(f"Starte WebSocket Server Thread auf Port {port}...")
    ws_thread = threading.Thread(target=run_loop, daemon=True, name="WebSocketServerThread")
    ws_thread.start()
    return ws_thread, stop_event


# --- WebSocket Client (für Streamer.bot) ---

async def streamerbot_websocket_client(websocket_url, sb_queue, stop_event, gui_q):
    """
    Verbindet sich mit dem Streamer.bot WebSocket und sendet Nachrichten aus der Queue.
    Verwendet eine vereinfachte Logik ohne explizite Ping/Status-Checks in der Schleife.
    """
    if not websockets:
        logger.error("WebSocket-Bibliothek nicht verfügbar. Streamer.bot Client kann nicht gestartet werden.")
        gui_q.put(("error", "WebSocket Lib fehlt!"))
        return

    while not stop_event.is_set():
        websocket = None
        try:
            logger.info(f"Versuche Verbindung zu Streamer.bot: {websocket_url}")
            websocket = await asyncio.wait_for(websockets.connect(websocket_url), timeout=10.0)
            logger.info(f"Verbunden mit Streamer.bot WebSocket: {websocket_url}")
            gui_q.put(("status", "Verbunden mit Streamer.bot"))

            # Hauptschleife während der Verbindung
            while not stop_event.is_set():
                message_json = None
                try:
                    # Versuche, eine Nachricht aus der Queue zu holen
                    message_json = await asyncio.to_thread(sb_queue.get, block=True, timeout=0.5)
                except queue.Empty:
                    # FIX: Wenn Queue leer ist, einfach kurz warten statt Ping/Check
                    await asyncio.sleep(0.1)
                    continue # Gehe zum nächsten Schleifendurchlauf

                # Wenn eine Nachricht geholt wurde, sende sie
                if message_json:
                    try:
                        # FIX: Keinen expliziten Check vor dem Senden
                        await websocket.send(message_json)
                        logger.debug(f"Nachricht an Streamer.bot gesendet: {message_json[:100]}...")
                        sb_queue.task_done()
                    except (websockets.exceptions.ConnectionClosed, ConnectionResetError):
                        # Fehler wird hier gefangen, wenn Verbindung beim Senden weg ist
                        logger.warning("Streamer.bot WS Verbindung geschlossen beim Senden.")
                        logger.error(f"Nachricht konnte nicht gesendet werden: {message_json[:100]}...")
                        # Evtl. Nachricht zurücklegen? sb_queue.put(message_json)
                        break # Verlasse innere Schleife -> Neuverbindungsversuch
                    except Exception as send_err:
                        logger.error(f"Fehler beim Senden an Streamer.bot: {send_err}")
                        gui_q.put(("warning", f"Fehler Senden an SB: {send_err}"))
                        await asyncio.sleep(1) # Warte kurz bei Sendefehler

        # --- Fehlerbehandlung für Verbindungsaufbau etc. (bleibt gleich) ---
        except websockets.exceptions.InvalidURI:
            logger.error(f"Ungültige Streamer.bot WebSocket URL: {websocket_url}")
            gui_q.put(("error", f"Ungültige SB URL: {websocket_url}"))
            stop_event.set()
        except (websockets.exceptions.ConnectionClosed, websockets.exceptions.ConnectionClosedError, ConnectionResetError) as conn_closed_err:
            logger.warning(f"Streamer.bot WS Verbindung geschlossen/zurückgesetzt: {conn_closed_err}")
            gui_q.put(("warning", "SB Verbindung getrennt."))
        except ConnectionRefusedError:
            logger.warning(f"Streamer.bot WS Verbindung verweigert: {websocket_url}. Läuft der SB Server? Ist die URL/Port korrekt?")
            gui_q.put(("warning", "SB WS Verbindung verweigert."))
        except asyncio.TimeoutError:
             logger.warning(f"Streamer.bot WS Verbindungsversuch Timeout (>10s): {websocket_url}")
             gui_q.put(("warning", "SB WS Verbindungs-Timeout."))
        except Exception as e:
            logger.exception("Unerwarteter Fehler im Streamer.bot WS Client")
            gui_q.put(("warning", f"SB WS Client Fehler: {e}"))
        finally:
             # Schließe Verbindung, falls sie noch offen ist (z.B. nach Timeout im Ping)
             # Verwende .open, da es wahrscheinlicher funktioniert als .closed/.state_name
             if websocket and websocket.open:
                  try:
                      await websocket.close()
                      logger.info("Streamer.bot WebSocket Verbindung explizit geschlossen.")
                  except Exception as close_err:
                       logger.error(f"Fehler beim expliziten Schließen der SB Verbindung: {close_err}")


        # Wartezeit vor Neuverbindung (bleibt gleich)
        if not stop_event.is_set():
            retry_delay = 10
            logger.info(f"Warte {retry_delay} Sekunden vor erneutem Verbindungsversuch mit Streamer.bot...")
            gui_q.put(("status", "Warte auf Streamer.bot..."))
            try:
                for _ in range(retry_delay):
                     if stop_event.is_set(): break
                     await asyncio.sleep(1)
            except asyncio.CancelledError:
                 logger.info("Streamer.bot Client Wartezeit abgebrochen.")
                 break

    logger.info("Streamer.bot WebSocket Client Task beendet.")
    gui_q.put(("status", "Streamer.bot Client gestoppt."))


def start_streamerbot_client_thread(websocket_url, sb_queue, stop_event, gui_q):
    """Startet den Streamer.bot WebSocket Client in einem separaten Thread."""
    # (Keine Änderungen in dieser Funktion nötig)
    loop = asyncio.new_event_loop()

    def run_loop():
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(streamerbot_websocket_client(websocket_url, sb_queue, stop_event, gui_q))
        except Exception as e:
             logger.exception("Fehler während der Ausführung des Streamer.bot Client Loops im Thread")
        finally:
            logger.info("Streamer.bot Client Loop im Thread beendet. Räume auf...")
            try:
                tasks = asyncio.all_tasks(loop=loop)
                for task in tasks:
                     if not task.done(): task.cancel()
                if loop.is_running():
                    loop.run_until_complete(asyncio.sleep(0.1, loop=loop))
            except RuntimeError as e:
                 if "cannot schedule new futures after shutdown" in str(e): logger.debug("SB Loop wurde bereits heruntergefahren.")
                 else: logger.error(f"Laufzeitfehler beim Aufräumen der asyncio Tasks im SB Client Thread: {e}")
            except Exception as e_cancel: logger.error(f"Fehler beim Aufräumen der asyncio Tasks im SB Client Thread: {e_cancel}")
            finally:
                 if not loop.is_closed():
                      if loop.is_running(): loop.stop()
                      loop.close()
                      logger.info("Streamer.bot Client Event Loop geschlossen.")
                 else: logger.info("Streamer.bot Client Event Loop war bereits geschlossen.")
                 logger.info("Streamer.bot Client Thread vollständig beendet.")

    logger.info(f"Starte Streamer.bot Client Thread für URL: {websocket_url}...")
    sb_thread = threading.Thread(target=run_loop, daemon=True, name="StreamerBotClientThread")
    sb_thread.start()
    return sb_thread

