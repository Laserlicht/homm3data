import os
import gettext

LOCALE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'locale')

_translations = {}

def get_translation(lang=None):
    if lang is None:
        lang = os.environ.get('LANG', 'en').split('.')[0].split('_')[0]
    
    if lang not in _translations:
        try:
            t = gettext.translation('homm3data', LOCALE_DIR, languages=[lang])
        except FileNotFoundError:
            t = gettext.NullTranslations()
        _translations[lang] = t
    
    return _translations[lang]

def _(s):
    lang = os.environ.get('LANG', 'en').split('.')[0].split('_')[0]
    return get_translation(lang).gettext(s)

AVAILABLE_LANGUAGES = {
    'en': 'English',
    'de': 'Deutsch',
}

def set_language(lang):
    os.environ['LANG'] = lang
    _translations.clear()
