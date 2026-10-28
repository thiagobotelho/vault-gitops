#!/usr/bin/env python3
"""Emite token curto para o operador. stdout contém credencial: não grave em logs."""
from vault_api import connection, login
with connection() as call:
    print(login(call))
