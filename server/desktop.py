"""Frozen desktop sidecar entry point. Keeps spawned download workers in this process."""
import multiprocessing
import os

import uvicorn

from server.app import app


def main():
    multiprocessing.freeze_support()
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=int(os.environ["PORT"]),
        access_log=False,
        log_level="warning",
    )


if __name__ == "__main__":
    main()
