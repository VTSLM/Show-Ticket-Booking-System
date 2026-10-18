"""
firebase_admin_setup.py — Initialise Firebase Admin SDK once at startup.
"""
import firebase_admin
from firebase_admin import credentials

from config import settings


import json
import os
import sys

def init_firebase() -> None:
    """Initialise the Firebase Admin app if it hasn't been initialised yet."""
    if firebase_admin._apps:
        return

    path = settings.firebase_service_account_path
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"\n[Firebase Setup Error] File '{path}' not found.\n"
            "Please download your service account private key JSON from Firebase Console:\n"
            "Project Settings -> Service accounts -> Generate new private key.\n"
        )

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as err:
        raise ValueError(
            f"\n[Firebase Setup Error] '{path}' is not valid JSON ({err}).\n"
            "You may have pasted JavaScript code (e.g. const firebaseConfig = {...}) instead of the JSON file.\n"
            "Please generate and download the private key JSON from:\n"
            "https://console.firebase.google.com/project/_/settings/serviceaccounts/adminsdk\n"
        ) from err

    if "private_key" not in data or "client_email" not in data:
        raise ValueError(
            f"\n[Firebase Setup Error] '{path}' is missing 'private_key' or 'client_email'.\n"
            "Please ensure you downloaded the Admin SDK private key JSON from Firebase Console,\n"
            "not the Web App Client configuration snippet.\n"
        )

    cred = credentials.Certificate(data)
    firebase_admin.initialize_app(cred)
