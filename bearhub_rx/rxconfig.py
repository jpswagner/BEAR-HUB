"""Reflex config for the BEAR-HUB app.

Run from this folder:

    reflex run

Frontend on :3200, backend on :8200.
"""
import reflex as rx

config = rx.Config(app_name="bearhub", frontend_port=3200, backend_port=8200)
