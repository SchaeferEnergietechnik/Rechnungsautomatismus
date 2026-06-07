from app.bootstrap import bootstrap_application
from app.env_loader import EnvLoader


def main() -> None:
    EnvLoader.load_from_file(".env")
    app_context = bootstrap_application()
    app_context.main_window.show()
    app_context.qt_app.exec()


if __name__ == "__main__":
    main()
