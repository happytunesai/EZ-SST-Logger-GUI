# -*- coding: utf-8 -*-
"""
Funktionen für WebSocket-Server (externe Steuerung) und Client (Streamer.bot).
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
from lib.constants import WEBSOCKET_PORT # Importiere Standardport

# Globale Referenzen für diesen Modul (optional, wenn Threads von außen verwaltet werden)
# websocket_server_thread = None
# streamerbot_client_thread = None
# websocket_stop_event_global = None # Wird von start_websocket_server_thread gesetzt

# --- WebSocket Server (für externe Steuerung) ---

async def websocket_handler(websocket, path, gui_q):
    """
    Behandelt eingehende WebSocket-Verbindungen und Nachrichten.
    Args:
        websocket: Das WebSocket-Verbindungsobjekt.
        path (str): Der angeforderte Pfad (oft nicht verwendet).
        gui_q (queue.Queue): Die Queue zum Senden von Befehlen an die GUI.
    """
    client_addr = websocket.remote_address
    logger.info(f"WebSocket Client verbunden: {client_addr}")
    try:
        # Verarbeite Nachrichten vom Client
        async for message in websocket:
            logger.info(f"WebSocket Nachricht empfangen von {client_addr}: {message}")
            if isinstance(message, str):
                command = message.strip().upper()
                if command == "TOGGLE_RECORD":
                    logger.info("WebSocket: Sende Start/Stop Signal an GUI...")
                    # Lege Befehl in die GUI-Queue zur threadsicheren Verarbeitung
                    gui_q.put(("toggle_recording_external", None))
                    await websocket.send("OK: TOGGLE_RECORD empfangen und weitergeleitet.")
                elif command == "PING":
                     await websocket.send("PONG") # Einfaches Keep-Alive
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
        # Logge alle anderen Ausnahmen, die im Handler auftreten
        logger.exception(f"WebSocket Fehler im Handler für Client {client_addr}")
    finally:
        # Logge, wenn der Verbindungs-Handler endet
        logger.info(f"WebSocket Verbindung geschlossen für: {client_addr}")

async def run_websocket_server(stop_event, port, gui_q):
    """
    Führt den WebSocket-Server aus, bis das stop_event gesetzt wird.
    Args:
        stop_event (asyncio.Event): Das Event zum Stoppen des Servers.
        port (int): Der Port, auf dem der Server lauschen soll.
        gui_q (queue.Queue): Die Queue zum Senden von Befehlen an die GUI.
    """
    host = "localhost" # Lausche standardmäßig nur auf localhost aus Sicherheitsgründen
    # Stelle sicher, dass die websockets-Bibliothek verfügbar ist
    if not websockets:
        logger.error("WebSocket-Bibliothek nicht verfügbar. Server kann nicht gestartet werden.")
        gui_q.put(("error", "WebSocket Lib fehlt!"))
        return

    server_instance = None # Referenz zum Server für sauberes Schließen
    try:
        # Erstelle den Handler mit der übergebenen gui_q
        handler_with_queue = lambda ws, path: websocket_handler(ws, path, gui_q)
        # Starte den Server
        server_instance = await websockets.serve(handler_with_queue, host, port)
        logger.info(f"WebSocket Server gestartet auf ws://{host}:{port}")
        gui_q.put(("status", f"WebSocket Server läuft auf Port {port}"))

        # Warte, bis das stop_event gesetzt wird
        await stop_event.wait()
        logger.info("WebSocket Server wird gestoppt (Stop-Event empfangen)...")

    except OSError as e:
        # Behandle häufige Fehler wie Port bereits belegt
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
    """
    Startet den WebSocket-Server in einem separaten Thread.
    Args:
        port (int): Der zu verwendende Port.
        gui_q (queue.Queue): Die GUI-Queue.
    Returns:
        tuple: (threading.Thread, asyncio.Event) oder (None, None) bei Fehler.
               Gibt den Thread und das Stop-Event zurück, damit es von außen gesetzt werden kann.
    """
    # Validiere Portnummer
    if not isinstance(port, int) or not 1 <= port <= 65535:
        logger.error(f"Ungültiger WebSocket Port angegeben: {port}. Server nicht gestartet.")
        gui_q.put(("error", f"Ungültiger WS Port: {port}"))
        return None, None

    # Erstelle eine neue Event-Loop für den Thread
    loop = asyncio.new_event_loop()
    # Erstelle das Stop-Event, das zu dieser Loop gehört
    # FIX: Entferne den 'loop=' Parameter (veraltet seit Python 3.10)
    stop_event = asyncio.Event()

    def run_loop():
        """Zielfunktion für den Thread, setzt die Loop und führt den Server aus."""
        asyncio.set_event_loop(loop)
        # Verknüpfe das Event mit der jetzt aktuellen Loop (wichtig für call_soon_threadsafe später)
        # Dies ist nicht mehr die Standardmethode, aber wir speichern die Loop-Referenz
        # setattr(stop_event, '_loop', loop) # Speichere die Loop am Event (alternativ global speichern)

        try:
            loop.run_until_complete(run_websocket_server(stop_event, port, gui_q))
        except Exception as e:
             logger.exception("Fehler während der Ausführung des WebSocket Server Loops im Thread")
        finally:
            logger.info("WebSocket Server Loop im Thread beendet. Räume auf...")
            try:
                # Beende verbleibende Tasks in der Loop sauber
                tasks = asyncio.all_tasks(loop=loop)
                for task in tasks:
                    if not task.done():
                         task.cancel()
                # Erlaube die Verarbeitung von Cancellations
                # Führe loop.run_until_complete nur aus, wenn die Loop noch läuft
                if loop.is_running():
                    loop.run_until_complete(asyncio.sleep(0.1, loop=loop))
                    # Sammle gecancelte Tasks, um Warnungen zu vermeiden
                    # loop.run_until_complete(asyncio.gather(*[t for t in tasks if not t.done()], return_exceptions=True)) # Nur nicht erledigte sammeln?
            except RuntimeError as e:
                 if "cannot schedule new futures after shutdown" in str(e):
                      logger.debug("Loop wurde bereits heruntergefahren, bevor Tasks gesammelt werden konnten.")
                 else:
                      logger.error(f"Laufzeitfehler beim Aufräumen der asyncio Tasks im WS Server Thread: {e}")
            except Exception as e_cancel:
                logger.error(f"Fehler beim Aufräumen der asyncio Tasks im WS Server Thread: {e_cancel}")
            finally:
                 if not loop.is_closed():
                      if loop.is_running():
                           loop.stop() # Stelle sicher, dass Loop stoppt, falls noch aktiv
                      loop.close() # Schließe die Event-Loop
                      logger.info("WebSocket Server Event Loop geschlossen.")
                 else:
                      logger.info("WebSocket Server Event Loop war bereits geschlossen.")
                 logger.info("WebSocket Server Thread vollständig beendet.")

    logger.info(f"Starte WebSocket Server Thread auf Port {port}...")
    ws_thread = threading.Thread(target=run_loop, daemon=True, name="WebSocketServerThread")
    # Speichere die Loop-Referenz, um sie später im Stop-Signal verwenden zu können
    # Dies ist eine Möglichkeit, die Loop zugänglich zu machen
    setattr(stop_event, '_custom_loop_ref', loop) # Hänge die Loop-Referenz an das Event
    ws_thread.start()

    return ws_thread, stop_event # Gebe Thread und Stop-Event zurück


# --- WebSocket Client (für Streamer.bot) ---

async def streamerbot_websocket_client(websocket_url, sb_queue, stop_event, gui_q):
    """
    Verbindet sich mit dem Streamer.bot WebSocket und sendet Nachrichten aus der Queue.
    Args:
        websocket_url (str): Die URL des Streamer.bot WebSocket Servers.
        sb_queue (queue.Queue): Die Queue mit zu sendenden Nachrichten (JSON-Strings).
        stop_event (threading.Event): Das Event zum Stoppen des Clients.
        gui_q (queue.Queue): Die Queue zum Senden von Status/Fehlern an die GUI.
    """
    # Stelle sicher, dass die websockets-Bibliothek verfügbar ist
    if not websockets:
        logger.error("WebSocket-Bibliothek nicht verfügbar. Streamer.bot Client kann nicht gestartet werden.")
        gui_q.put(("error", "WebSocket Lib fehlt!"))
        return

    while not stop_event.is_set():
        websocket = None # Definiere außerhalb des try-Blocks für finally
        try:
            logger.info(f"Versuche Verbindung zu Streamer.bot: {websocket_url}")
            # Stelle Verbindung mit Timeout her
            websocket = await asyncio.wait_for(websockets.connect(websocket_url), timeout=10.0)
            logger.info(f"Verbunden mit Streamer.bot WebSocket: {websocket_url}")
            gui_q.put(("status", "Verbunden mit Streamer.bot"))

            # Hauptschleife während der Verbindung
            while not stop_event.is_set():
                message_json = None
                try:
                    # Versuche, eine Nachricht aus der Queue zu holen (blockierend mit Timeout)
                    # Verwende asyncio.to_thread für threadsicheren Queue-Zugriff aus async Kontext
                    # Gib die Kontrolle frei, während auf die Queue gewartet wird
                    message_json = await asyncio.to_thread(sb_queue.get, block=True, timeout=0.5)
                except queue.Empty:
                    # Keine Nachricht in der Queue, prüfe Verbindungsstatus mit Ping
                    try:
                        if websocket.closed: # Prüfe explizit, ob geschlossen
                             logger.warning("Streamer.bot WS Verbindung ist geschlossen (vor Ping).")
                             break
                        pong_waiter = await websocket.ping()
                        # Warte auf die Pong-Antwort mit Timeout
                        await asyncio.wait_for(pong_waiter, timeout=5)
                        # logger.debug("Streamer.bot Ping erfolgreich.")
                    except asyncio.TimeoutError:
                        logger.warning("Streamer.bot WebSocket Ping Timeout - Verbindung vermutlich verloren.")
                        break # Verlasse innere Schleife zum Neuverbinden
                    except (websockets.exceptions.ConnectionClosed, ConnectionResetError):
                        logger.warning("Streamer.bot WS Verbindung geschlossen während Warten auf Pong.")
                        break # Verlasse innere Schleife zum Neuverbinden
                    except Exception as ping_err:
                         logger.error(f"Fehler während Streamer.bot Ping: {ping_err}")
                         # Hier evtl. auch break?
                         await asyncio.sleep(1) # Warte kurz bei Ping-Fehler
                    continue # Setze Schleife fort, wenn Ping erfolgreich war

                # Wenn eine Nachricht geholt wurde, sende sie
                if message_json:
                    try:
                        if websocket.closed: # Prüfe erneut vor dem Senden
                             logger.warning("Streamer.bot WS Verbindung ist geschlossen (vor Senden).")
                             # Nachricht zurück in die Queue?
                             # sb_queue.put(message_json) # Vorsicht vor Endlosschleife
                             break
                        await websocket.send(message_json)
                        logger.debug(f"Nachricht an Streamer.bot gesendet: {message_json[:100]}...")
                        sb_queue.task_done() # Markiere Nachricht als verarbeitet in der Queue
                    except (websockets.exceptions.ConnectionClosed, ConnectionResetError):
                        logger.warning("Streamer.bot WS Verbindung geschlossen beim Senden.")
                        logger.error(f"Nachricht konnte nicht gesendet werden: {message_json[:100]}...")
                        # Nachricht zurücklegen?
                        # sb_queue.put(message_json)
                        break # Verlasse innere Schleife zum Neuverbinden
                    except Exception as send_err:
                        logger.error(f"Fehler beim Senden an Streamer.bot: {send_err}")
                        gui_q.put(("warning", f"Fehler Senden an SB: {send_err}"))
                        # Warte kurz, bevor erneut versucht wird oder abgebrochen wird
                        await asyncio.sleep(1)
                        # Hier evtl. auch break, je nach Fehlertyp

        except websockets.exceptions.InvalidURI:
            logger.error(f"Ungültige Streamer.bot WebSocket URL: {websocket_url}")
            gui_q.put(("error", f"Ungültige SB URL: {websocket_url}"))
            stop_event.set() # Stoppe Versuche, wenn URL grundsätzlich falsch ist
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
             # Stelle sicher, dass die Verbindung geschlossen wird, wenn wir aus der Schleife fallen
             if websocket and not websocket.closed:
                  await websocket.close()
                  logger.info("Streamer.bot WebSocket Verbindung explizit geschlossen.")


        # Warte, bevor ein neuer Verbindungsversuch gestartet wird, falls das Stop-Event nicht gesetzt ist
        if not stop_event.is_set():
            retry_delay = 10
            logger.info(f"Warte {retry_delay} Sekunden vor erneutem Verbindungsversuch mit Streamer.bot...")
            gui_q.put(("status", "Warte auf Streamer.bot..."))
            try:
                # Verwende asyncio.sleep und behandle mögliche Cancellation während des Wartens
                # Prüfe stop_event periodisch während des Schlafens
                for _ in range(retry_delay):
                     if stop_event.is_set():
                          break
                     await asyncio.sleep(1)
            except asyncio.CancelledError:
                 logger.info("Streamer.bot Client Wartezeit abgebrochen.")
                 # Breche die äußere Schleife ab, wenn gecancelt wurde
                 break

    logger.info("Streamer.bot WebSocket Client Task beendet.")
    gui_q.put(("status", "Streamer.bot Client gestoppt."))


def start_streamerbot_client_thread(websocket_url, sb_queue, stop_event, gui_q):
    """
    Startet den Streamer.bot WebSocket Client in einem separaten Thread.
    Args:
        websocket_url (str): Die URL des Streamer.bot Servers.
        sb_queue (queue.Queue): Die Queue mit zu sendenden Nachrichten.
        stop_event (threading.Event): Das Event zum Stoppen des Threads.
        gui_q (queue.Queue): Die GUI-Queue.
    Returns:
        threading.Thread: Der gestartete Thread oder None bei Fehler.
    """
    # Erstelle eine neue Event-Loop für den Thread
    loop = asyncio.new_event_loop()

    def run_loop():
        """Zielfunktion für den Thread."""
        asyncio.set_event_loop(loop)
        try:
            # Führe die Client-Coroutine aus, bis sie endet (wenn stop_event gesetzt wird)
            loop.run_until_complete(streamerbot_websocket_client(websocket_url, sb_queue, stop_event, gui_q))
        except Exception as e:
             logger.exception("Fehler während der Ausführung des Streamer.bot Client Loops im Thread")
        finally:
            logger.info("Streamer.bot Client Loop im Thread beendet. Räume auf...")
            try:
                # Beende verbleibende Tasks sauber
                tasks = asyncio.all_tasks(loop=loop)
                for task in tasks:
                     if not task.done():
                          task.cancel()
                if loop.is_running():
                    loop.run_until_complete(asyncio.sleep(0.1, loop=loop))
                    # loop.run_until_complete(asyncio.gather(*[t for t in tasks if not t.done()], return_exceptions=True))
            except RuntimeError as e:
                 if "cannot schedule new futures after shutdown" in str(e):
                      logger.debug("SB Loop wurde bereits heruntergefahren, bevor Tasks gesammelt werden konnten.")
                 else:
                      logger.error(f"Laufzeitfehler beim Aufräumen der asyncio Tasks im SB Client Thread: {e}")
            except Exception as e_cancel:
                logger.error(f"Fehler beim Aufräumen der asyncio Tasks im SB Client Thread: {e_cancel}")
            finally:
                 if not loop.is_closed():
                      if loop.is_running():
                           loop.stop()
                      loop.close()
                      logger.info("Streamer.bot Client Event Loop geschlossen.")
                 else:
                      logger.info("Streamer.bot Client Event Loop war bereits geschlossen.")
                 logger.info("Streamer.bot Client Thread vollständig beendet.")

    logger.info(f"Starte Streamer.bot Client Thread für URL: {websocket_url}...")
    sb_thread = threading.Thread(target=run_loop, daemon=True, name="StreamerBotClientThread")
    sb_thread.start()
    return sb_thread

