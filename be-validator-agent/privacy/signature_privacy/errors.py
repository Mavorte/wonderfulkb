"""Chyby knihovny. Zprávy nikdy neobsahují klíče, data ani obsah bloku."""


class PrivacyError(Exception):
    pass


class InvalidContext(PrivacyError):
    """Kontext chybí nebo má špatný tvar (chybí case_id, document_id nebo signature_id)."""


class DecryptionError(PrivacyError):
    """Blok nejde dešifrovat: poškozený, špatný kontext, špatný klíč nebo neznámá verze.

    Důvod se záměrně nerozlišuje, ať chyba nefunguje jako věštec pro útočníka."""
