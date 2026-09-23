import sqlite3

from langgraph.checkpoint.sqlite import SqliteSaver

from agent.settings import CHECKPOINT_PATH

_checkpointer = None


def get_checkpointer():
    global _checkpointer
    if _checkpointer is None:
        connection = sqlite3.connect(str(CHECKPOINT_PATH), check_same_thread=False)
        _checkpointer = SqliteSaver(connection)
        _checkpointer.setup()
    return _checkpointer
