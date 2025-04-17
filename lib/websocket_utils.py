# -*- coding: utf-8 -*-
"""
WebSocket server (external control) and client (Streamer.bot) utilities.
This version addresses known issues for both variants.
"""
import asyncio
import threading
import queue
import json

try:
    import websockets
except ImportError:
    websockets = None

from lib.logger_setup import logger
from lib.constants import WEBSOCKET_PORT

try:
    from lib.language_manager import tr
except ImportError:
    def tr(key, **kwargs): return key.format(**kwargs) if kwargs else key

# --- WebSocket Server ---

async def websocket_handler(websocket, gui_q):
    """Handles a single WebSocket connection."""
    client_addr = websocket.remote_address
    logger.info(tr("log_ws_client_connected", addr=client_addr))
    try:
        async for message in websocket:
            logger.info(tr("log_ws_message_received", addr=client_addr, msg=message))
            if isinstance(message, str):
                command = message.strip().upper()
                if command == "TOGGLE_RECORD":
                    logger.info(tr("log_ws_command_toggle"))
                    gui_q.put(("toggle_recording_external", None))
                    gui_q.put(("ws_state", "connected"))
                    await websocket.send("OK: TOGGLE_RECORD received and forwarded.")
                elif command == "PING":
                    await websocket.send("PONG")
                else:
                    logger.warning(tr("log_ws_command_unknown", cmd=message, addr=client_addr))
                    await websocket.send(tr("log_ws_error_unknown_command", cmd=message))
            else:
                logger.warning(tr("log_ws_non_text_message", addr=client_addr))
                await websocket.send(tr("log_ws_error_only_text"))
    except websockets.exceptions.ConnectionClosedOK:
        logger.info(tr("log_ws_client_disconnected_ok", addr=client_addr))
    except websockets.exceptions.ConnectionClosedError as ws_err:
        logger.warning(tr("log_ws_client_disconnected_error", addr=client_addr, error=str(ws_err)))
    except Exception:
        logger.exception(tr("log_ws_handler_exception", addr=client_addr))
    finally:
        logger.info(tr("log_ws_connection_closed", addr=client_addr))


async def run_websocket_server(stop_event, port, gui_q):
    """Runs the WebSocket server until stop_event is triggered."""
    host = "localhost"
    if not websockets:
        logger.error(tr("log_ws_lib_missing"))
        gui_q.put(("error", tr("status_error_ws_lib_missing")))
        return

    server_instance = None
    try:
        handler = lambda ws, _path=None: websocket_handler(ws, gui_q)
        server_instance = await websockets.serve(handler, host, port)
        logger.info(tr("log_ws_server_started", host=host, port=port))
        gui_q.put(("status", tr("status_ws_server_running", port=port)))
        gui_q.put(("ws_state", "connected"))
        await stop_event.wait()
        logger.info(tr("log_ws_server_stopping"))
    except OSError as e:
        if "address already in use" in str(e).lower():
            logger.error(tr("log_ws_port_in_use", port=port))
            gui_q.put(("error", tr("status_error_ws_port_busy", port=port)))
        else:
            logger.error(tr("log_ws_port_error", port=port, error=str(e)))
            gui_q.put(("error", tr("status_error_ws_other", port=port, error=str(e))))
    except Exception as e:
        logger.exception(tr("log_ws_server_exception"))
        gui_q.put(("error", tr("status_error_ws_server_task", error=str(e))))
    finally:
        if server_instance:
            server_instance.close()
            await server_instance.wait_closed()
            logger.info(tr("log_ws_server_closed"))
        logger.info(tr("log_ws_server_task_ended"))
        gui_q.put(("status", tr("status_ws_server_stopped")))
        gui_q.put(("ws_state", "disabled"))



def start_websocket_server_thread(port, gui_q):
    """Starts the WebSocket server in a separate thread."""
    if not isinstance(port, int) or not 1 <= port <= 65535:
        logger.error(tr("log_ws_invalid_port", port=port))
        gui_q.put(("error", tr("status_error_ws_port_invalid", port=port)))
        return None, None

    loop = asyncio.new_event_loop()
    stop_event = asyncio.Event()

    def run_loop():
        asyncio.set_event_loop(loop)
        setattr(stop_event, '_custom_loop_ref', loop)
        try:
            loop.run_until_complete(run_websocket_server(stop_event, port, gui_q))
        except Exception:
            logger.exception(tr("log_ws_loop_exception"))
        finally:
            logger.info(tr("log_ws_loop_cleanup"))
            try:
                tasks = asyncio.all_tasks(loop=loop)
                for task in tasks:
                    if not task.done():
                        task.cancel()
                if loop.is_running():
                    loop.run_until_complete(asyncio.sleep(0.1, loop=loop))
            except RuntimeError as e:
                if "cannot schedule new futures after shutdown" in str(e):
                    logger.debug(tr("log_ws_loop_already_shutdown"))
                else:
                    logger.error(tr("log_ws_loop_runtime_error", error=str(e)))
            except Exception as e_cancel:
                logger.error(tr("log_ws_loop_cancel_error", error=str(e_cancel)))
            finally:
                if not loop.is_closed():
                    if loop.is_running():
                        loop.stop()
                    loop.close()
                    logger.info(tr("log_ws_loop_closed"))
                else:
                    logger.info(tr("log_ws_loop_already_closed"))
                logger.info(tr("log_ws_thread_done"))

    logger.info(tr("log_ws_thread_starting", port=port))
    ws_thread = threading.Thread(target=run_loop, daemon=True, name="WebSocketServerThread")
    ws_thread.start()
    return ws_thread, stop_event


# --- WebSocket Client (Streamer.bot) ---

async def streamerbot_websocket_client(websocket_url, sb_queue, stop_event, gui_q):
    """Connects to the Streamer.bot WebSocket and sends queued messages."""
    if not websockets:
        logger.error(tr("log_sb_lib_missing"))
        gui_q.put(("error", tr("status_error_ws_lib_missing")))
        return

    while not stop_event.is_set():
        websocket = None
        try:
            logger.info(tr("log_sb_connecting", url=websocket_url))
            gui_q.put(("sb_state", "connecting"))
            websocket = await asyncio.wait_for(websockets.connect(websocket_url), timeout=10.0)
            logger.info(tr("log_sb_connected", url=websocket_url))
            gui_q.put(("sb_state", "connected"))
            gui_q.put(("status", tr("status_sb_client_connected")))

            while not stop_event.is_set():
                message_json = None
                try:
                    message_json = await asyncio.to_thread(sb_queue.get, block=True, timeout=0.5)
                except queue.Empty:
                    try:
                        pong_waiter = await websocket.ping()
                        await asyncio.wait_for(pong_waiter, timeout=5)
                    except (asyncio.TimeoutError, websockets.exceptions.ConnectionClosed, ConnectionResetError):
                        logger.warning(tr("log_sb_ping_failed"))
                        break
                    except Exception as ping_err:
                        logger.error(tr("log_sb_ping_error", error=str(ping_err)))
                        await asyncio.sleep(1)
                    await asyncio.sleep(0.1)
                    continue

                if message_json:
                    try:
                        await websocket.send(message_json)
                        logger.debug(tr("log_sb_message_sent", msg_preview=message_json[:100]))
                        sb_queue.task_done()
                    except (websockets.exceptions.ConnectionClosed, ConnectionResetError):
                        logger.warning(tr("log_sb_send_closed"))
                        logger.error(tr("log_sb_send_failed", msg_preview=message_json[:100]))
                        break
                    except Exception as send_err:
                        logger.error(tr("log_sb_send_error", error=str(send_err)))
                        gui_q.put(("warning", tr("status_sb_warn_send_error", error=str(send_err))))
                        await asyncio.sleep(1)

        except websockets.exceptions.InvalidURI:
            logger.error(tr("log_sb_invalid_url", url=websocket_url))
            gui_q.put(("error", tr("status_error_sb_url_invalid", url=websocket_url)))
            stop_event.set()
        except (websockets.exceptions.ConnectionClosed, websockets.exceptions.ConnectionClosedError, ConnectionResetError) as conn_closed_err:
            logger.warning(tr("log_sb_connection_closed", error=str(conn_closed_err)))
            gui_q.put(("warning", tr("status_sb_warn_disconnected")))
        except ConnectionRefusedError:
            logger.warning(tr("log_sb_connection_refused", url=websocket_url))
            gui_q.put(("warning", tr("status_sb_warn_refused")))
        except asyncio.TimeoutError:
            logger.warning(tr("log_sb_connection_timeout", url=websocket_url))
            gui_q.put(("warning", tr("status_sb_warn_timeout")))
        except Exception as e:
            logger.exception(tr("log_sb_unexpected_exception"))
            gui_q.put(("warning", tr("status_error_sb_client_task", error=str(e))))
        finally:
            if websocket:
                try:
                    await websocket.close()
                    logger.info(tr("log_sb_connection_closed_explicit"))
                except Exception as close_err:
                    logger.error(tr("log_sb_connection_close_error", error=str(close_err)))

        if not stop_event.is_set():
            retry_delay = 10
            logger.info(tr("log_sb_retry_delay", seconds=retry_delay))
            gui_q.put(("status", tr("status_sb_client_waiting")))
            try:
                for _ in range(retry_delay):
                    if stop_event.is_set():
                        break
                    await asyncio.sleep(1)
            except asyncio.CancelledError:
                logger.info(tr("log_sb_cancelled"))
                break

    logger.info(tr("log_sb_task_ended"))
    gui_q.put(("sb_state", "disabled"))
    gui_q.put(("status", tr("status_sb_client_stopped")))


def start_streamerbot_client_thread(websocket_url, sb_queue, stop_event, gui_q):
    """Starts the Streamer.bot WebSocket client in a separate thread."""
    loop = asyncio.new_event_loop()
    def run_loop():
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(streamerbot_websocket_client(websocket_url, sb_queue, stop_event, gui_q))
        except Exception:
            logger.exception(tr("log_sb_loop_exception"))
        finally:
            logger.info(tr("log_sb_loop_cleanup"))
            try:
                tasks = asyncio.all_tasks(loop=loop)
                for task in tasks:
                    if not task.done():
                        task.cancel()
                if loop.is_running():
                    loop.run_until_complete(asyncio.sleep(0.1, loop=loop))
            except RuntimeError as e:
                if "cannot schedule new futures after shutdown" in str(e):
                    logger.debug(tr("log_sb_loop_already_shutdown"))
                else:
                    logger.error(tr("log_sb_loop_runtime_error", error=str(e)))
            except Exception as e_cancel:
                logger.error(tr("log_sb_loop_cancel_error", error=str(e_cancel)))
            finally:
                if not loop.is_closed():
                    if loop.is_running():
                        loop.stop()
                    loop.close()
                    logger.info(tr("log_sb_loop_closed"))
                else:
                    logger.info(tr("log_sb_loop_already_closed"))
                logger.info(tr("log_sb_thread_done"))
    logger.info(tr("log_sb_thread_starting", url=websocket_url))
    sb_thread = threading.Thread(target=run_loop, daemon=True, name="StreamerBotClientThread")
    sb_thread.start()
    return sb_thread
