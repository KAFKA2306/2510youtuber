"""Compatibility entry point for environment verification."""

from app.core.verify import SystemVerifier, main

__all__ = ["SystemVerifier", "main"]

if __name__ == "__main__":
    main()
