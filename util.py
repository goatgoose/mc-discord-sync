import asyncio
import logging


def _handle_task_result(task):
    try:
        task.result()
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logging.exception(e)


def create_task(coro):
    task = asyncio.create_task(coro)
    task.add_done_callback(_handle_task_result)
    return task
