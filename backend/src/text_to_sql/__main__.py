import os

import uvicorn


def main() -> None:
    port = int(os.environ.get("TEXT_TO_SQL_PORT", "8000"))
    uvicorn.run("text_to_sql.api:app", host="127.0.0.1", port=port)


if __name__ == "__main__":
    main()
