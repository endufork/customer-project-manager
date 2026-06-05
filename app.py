import os

import uvicorn


def main() -> None:
    port = int(os.environ.get("CUSTOMER_PROJECT_PORT", "8765"))
    uvicorn.run("customer_m.fastapi_app:app", host="127.0.0.1", port=port)


if __name__ == "__main__":
    main()
