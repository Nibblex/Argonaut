"""Interface internationalization: per-language strings, current language
and preference persistence with QSettings.

English is the default language and acts as a fallback: if a language is
missing a key, the English string is used.
"""

from PyQt5.QtCore import QSettings

DEFAULT = "en"

# code -> name shown in the menu (in its own language)
LANGUAGES = [
    ("en", "English"),
    ("es", "Español"),
    ("fr", "Français"),
    ("de", "Deutsch"),
    ("it", "Italiano"),
    ("pt", "Português"),
]

STRINGS = {
    "en": {
        "app_title": "Argonaut — Documents",
        "menu_language": "&Language",
        "detect_language": "Detect language",
        "swap_tooltip": "Swap languages",
        "hint": "Drag files here or use “Add…”  ·  Formats: {formats}",
        "add": "Add…",
        "remove": "Remove",
        "clear": "Clear",
        "output": "Output…",
        "output_tooltip": "Choose the folder where translations are saved",
        "output_default": "Next to each original",
        "output_open_tooltip": "Open the destination folder",
        "output_reset_tooltip": "Save next to each original again",
        "open": "Open",
        "open_tooltip": "Open the selected files",
        "menu_engine": "&Engine",
        "engine_nllb": "NLLB-200 (higher quality)",
        "nllb_download_title": "NLLB-200 model",
        "nllb_download_msg": "The NLLB-200 engine needs a one-time download "
                             "of about {size} MB. Download it now?",
        "downloading_model": "Downloading the NLLB-200 model…",
        "download_failed": "The download failed: {error}",
        "engine_status": "Engine: {name}",
        "nllb_remove": "Delete the NLLB-200 model…",
        "nllb_remove_msg": "This will delete the downloaded model "
                           "(~{size} MB) from disk. Continue?",
        "nllb_removed": "NLLB-200 model deleted.",
        "ready": "Ready.",
        "clear_status": "Dismiss",
        "clear_status_tooltip": "Dismiss the summary",
        "translate": "Translate",
        "cancel": "Cancel",
        "no_packages": "No language packages installed. Install one with:\n"
                       "argospm update && argospm install translate-en_es",
        "select_documents": "Select documents",
        "documents_filter": "Documents ({patterns})",
        "output_dir_title": "Output folder",
        "no_files_title": "No files",
        "no_files_msg": "Add at least one document.",
        "languages_title": "Languages",
        "same_language": "Source and target languages are the same.",
        "no_model_title": "No model",
        "no_model_msg": "No model installed to translate from {src} to {dst}.",
        "cancelling": "Cancelling…",
        "translating": "Translating {name}… (file {index} of {total})",
        "detected": "language detected: {name}",
        "cancelled": "Operation cancelled.",
        "translated_header": "Translated:",
        "errors_header": "Errors:",
        "err_detect": "{name}: could not detect the language",
        "err_already": "{name}: the document is already in {lang}",
        "err_no_model": "{name}: no model {src} → {dst}",
        "generating": "Generating {name}… page {done} of {total}",
        "saving": "Saving {name}…",
        "menu_help": "&Help",
        "about": "About Argonaut…",
        "about_title": "About Argonaut",
        "about_text": "<h3>Argonaut {version}</h3>"
                      "<p>Minimalist offline document translator.</p>"
                      "<p>Translation runs entirely on your computer using "
                      "<a href='https://www.argosopentech.com/'>Argos Translate</a> and "
                      "<a href='https://github.com/LibreTranslate/argos-translate-files'>argos-translate-files</a>; "
                      "your documents never leave your machine.</p>"
                      "<p>Supported formats: {formats}</p>"
                      "<p><a href='https://github.com/Nibblex/Argonaut'>Source "
                      "code on GitHub</a></p>"
                      "<p>© 2026 Sergio Rodríguez · Released under the "
                      "<a href='https://choosealicense.com/licenses/gpl-3.0/'>GNU GPL v3</a> "
                      "license.</p>",
    },
    "es": {
        "app_title": "Argonaut — Documentos",
        "menu_language": "&Idioma",
        "detect_language": "Detectar idioma",
        "swap_tooltip": "Intercambiar idiomas",
        "hint": "Arrastra archivos aquí o usa «Añadir…»  ·  Formatos: {formats}",
        "add": "Añadir…",
        "remove": "Quitar",
        "clear": "Vaciar",
        "output": "Destino…",
        "output_tooltip": "Elegir carpeta donde guardar las traducciones",
        "output_default": "Junto a cada original",
        "output_open_tooltip": "Abrir la carpeta de destino",
        "output_reset_tooltip": "Volver a guardar junto a cada original",
        "open": "Abrir",
        "open_tooltip": "Abrir los archivos seleccionados",
        "menu_engine": "&Motor",
        "engine_nllb": "NLLB-200 (mayor calidad)",
        "nllb_download_title": "Modelo NLLB-200",
        "nllb_download_msg": "El motor NLLB-200 requiere una descarga única "
                             "de unos {size} MB. ¿Descargarlo ahora?",
        "downloading_model": "Descargando el modelo NLLB-200…",
        "download_failed": "La descarga falló: {error}",
        "engine_status": "Motor: {name}",
        "nllb_remove": "Eliminar el modelo NLLB-200…",
        "nllb_remove_msg": "Se eliminará el modelo descargado (~{size} MB) "
                           "del disco. ¿Continuar?",
        "nllb_removed": "Modelo NLLB-200 eliminado.",
        "ready": "Listo.",
        "clear_status": "Limpiar",
        "clear_status_tooltip": "Limpiar el resumen",
        "translate": "Traducir",
        "cancel": "Cancelar",
        "no_packages": "No hay paquetes de idioma instalados. Instálalos con:\n"
                       "argospm update && argospm install translate-en_es",
        "select_documents": "Seleccionar documentos",
        "documents_filter": "Documentos ({patterns})",
        "output_dir_title": "Carpeta destino",
        "no_files_title": "Sin archivos",
        "no_files_msg": "Añade al menos un documento.",
        "languages_title": "Idiomas",
        "same_language": "El idioma de origen y destino son el mismo.",
        "no_model_title": "Sin modelo",
        "no_model_msg": "No hay un modelo instalado para traducir de {src} a {dst}.",
        "cancelling": "Cancelando…",
        "translating": "Traduciendo {name}… (archivo {index} de {total})",
        "detected": "idioma detectado: {name}",
        "cancelled": "Operación cancelada.",
        "translated_header": "Traducidos:",
        "errors_header": "Errores:",
        "err_detect": "{name}: no se pudo detectar el idioma",
        "err_already": "{name}: el documento ya está en {lang}",
        "err_no_model": "{name}: no hay modelo {src} → {dst}",
        "generating": "Generando {name}… página {done} de {total}",
        "saving": "Guardando {name}…",
        "menu_help": "A&yuda",
        "about": "Acerca de Argonaut…",
        "about_title": "Acerca de Argonaut",
        "about_text": "<h3>Argonaut {version}</h3>"
                      "<p>Traductor de documentos minimalista y sin conexión.</p>"
                      "<p>La traducción se realiza íntegramente en tu equipo con "
                      "<a href='https://www.argosopentech.com/'>Argos Translate</a> y "
                      "<a href='https://github.com/LibreTranslate/argos-translate-files'>argos-translate-files</a>; "
                      "tus documentos nunca salen de tu máquina.</p>"
                      "<p>Formatos soportados: {formats}</p>"
                      "<p><a href='https://github.com/Nibblex/Argonaut'>Código "
                      "fuente en GitHub</a></p>"
                      "<p>© 2026 Sergio Rodríguez · Publicado bajo la licencia "
                      "<a href='https://choosealicense.com/licenses/gpl-3.0/'>GNU GPL v3</a>.</p>",
    },
    "fr": {
        "app_title": "Argonaut — Documents",
        "menu_language": "&Langue",
        "detect_language": "Détecter la langue",
        "swap_tooltip": "Inverser les langues",
        "hint": "Glissez des fichiers ici ou utilisez « Ajouter… »  ·  Formats : {formats}",
        "add": "Ajouter…",
        "remove": "Retirer",
        "clear": "Vider",
        "output": "Destination…",
        "output_tooltip": "Choisir le dossier où enregistrer les traductions",
        "output_default": "À côté de chaque original",
        "output_open_tooltip": "Ouvrir le dossier de destination",
        "output_reset_tooltip": "Enregistrer de nouveau à côté de chaque original",
        "open": "Ouvrir",
        "open_tooltip": "Ouvrir les fichiers sélectionnés",
        "menu_engine": "Mo&teur",
        "engine_nllb": "NLLB-200 (meilleure qualité)",
        "nllb_download_title": "Modèle NLLB-200",
        "nllb_download_msg": "Le moteur NLLB-200 nécessite un téléchargement "
                             "unique d'environ {size} Mo. Le télécharger "
                             "maintenant ?",
        "downloading_model": "Téléchargement du modèle NLLB-200…",
        "download_failed": "Le téléchargement a échoué : {error}",
        "engine_status": "Moteur : {name}",
        "nllb_remove": "Supprimer le modèle NLLB-200…",
        "nllb_remove_msg": "Le modèle téléchargé (~{size} Mo) sera supprimé "
                           "du disque. Continuer ?",
        "nllb_removed": "Modèle NLLB-200 supprimé.",
        "ready": "Prêt.",
        "clear_status": "Effacer",
        "clear_status_tooltip": "Effacer le résumé",
        "translate": "Traduire",
        "cancel": "Annuler",
        "no_packages": "Aucun paquet de langue installé. Installez-en un avec :\n"
                       "argospm update && argospm install translate-en_es",
        "select_documents": "Sélectionner des documents",
        "documents_filter": "Documents ({patterns})",
        "output_dir_title": "Dossier de destination",
        "no_files_title": "Aucun fichier",
        "no_files_msg": "Ajoutez au moins un document.",
        "languages_title": "Langues",
        "same_language": "Les langues source et cible sont identiques.",
        "no_model_title": "Aucun modèle",
        "no_model_msg": "Aucun modèle installé pour traduire de {src} vers {dst}.",
        "cancelling": "Annulation…",
        "translating": "Traduction de {name}… (fichier {index} sur {total})",
        "detected": "langue détectée : {name}",
        "cancelled": "Opération annulée.",
        "translated_header": "Traduits :",
        "errors_header": "Erreurs :",
        "err_detect": "{name} : impossible de détecter la langue",
        "err_already": "{name} : le document est déjà en {lang}",
        "err_no_model": "{name} : aucun modèle {src} → {dst}",
        "generating": "Génération de {name}… page {done} sur {total}",
        "saving": "Enregistrement de {name}…",
        "menu_help": "Aid&e",
        "about": "À propos d'Argonaut…",
        "about_title": "À propos d'Argonaut",
        "about_text": "<h3>Argonaut {version}</h3>"
                      "<p>Traducteur de documents minimaliste et hors ligne.</p>"
                      "<p>La traduction s'effectue entièrement sur votre ordinateur avec "
                      "<a href='https://www.argosopentech.com/'>Argos Translate</a> et "
                      "<a href='https://github.com/LibreTranslate/argos-translate-files'>argos-translate-files</a> ; "
                      "vos documents ne quittent jamais votre machine.</p>"
                      "<p>Formats pris en charge : {formats}</p>"
                      "<p><a href='https://github.com/Nibblex/Argonaut'>Code "
                      "source sur GitHub</a></p>"
                      "<p>© 2026 Sergio Rodríguez · Publié sous licence "
                      "<a href='https://choosealicense.com/licenses/gpl-3.0/'>GNU GPL v3</a>.</p>",
    },
    "de": {
        "app_title": "Argonaut — Dokumente",
        "menu_language": "&Sprache",
        "detect_language": "Sprache erkennen",
        "swap_tooltip": "Sprachen tauschen",
        "hint": "Dateien hierher ziehen oder „Hinzufügen…“ verwenden  ·  Formate: {formats}",
        "add": "Hinzufügen…",
        "remove": "Entfernen",
        "clear": "Leeren",
        "output": "Zielordner…",
        "output_tooltip": "Ordner wählen, in dem die Übersetzungen gespeichert werden",
        "output_default": "Neben jedem Original",
        "output_open_tooltip": "Zielordner öffnen",
        "output_reset_tooltip": "Wieder neben jedem Original speichern",
        "open": "Öffnen",
        "open_tooltip": "Die ausgewählten Dateien öffnen",
        "menu_engine": "&Engine",
        "engine_nllb": "NLLB-200 (höhere Qualität)",
        "nllb_download_title": "NLLB-200-Modell",
        "nllb_download_msg": "Die NLLB-200-Engine benötigt einen einmaligen "
                             "Download von etwa {size} MB. Jetzt "
                             "herunterladen?",
        "downloading_model": "NLLB-200-Modell wird heruntergeladen…",
        "download_failed": "Der Download ist fehlgeschlagen: {error}",
        "engine_status": "Engine: {name}",
        "nllb_remove": "NLLB-200-Modell löschen…",
        "nllb_remove_msg": "Das heruntergeladene Modell (~{size} MB) wird "
                           "von der Festplatte gelöscht. Fortfahren?",
        "nllb_removed": "NLLB-200-Modell gelöscht.",
        "ready": "Bereit.",
        "clear_status": "Ausblenden",
        "clear_status_tooltip": "Zusammenfassung ausblenden",
        "translate": "Übersetzen",
        "cancel": "Abbrechen",
        "no_packages": "Keine Sprachpakete installiert. Installation mit:\n"
                       "argospm update && argospm install translate-en_es",
        "select_documents": "Dokumente auswählen",
        "documents_filter": "Dokumente ({patterns})",
        "output_dir_title": "Zielordner",
        "no_files_title": "Keine Dateien",
        "no_files_msg": "Füge mindestens ein Dokument hinzu.",
        "languages_title": "Sprachen",
        "same_language": "Ausgangs- und Zielsprache sind identisch.",
        "no_model_title": "Kein Modell",
        "no_model_msg": "Kein Modell installiert, um von {src} nach {dst} zu übersetzen.",
        "cancelling": "Wird abgebrochen…",
        "translating": "Übersetze {name}… (Datei {index} von {total})",
        "detected": "erkannte Sprache: {name}",
        "cancelled": "Vorgang abgebrochen.",
        "translated_header": "Übersetzt:",
        "errors_header": "Fehler:",
        "err_detect": "{name}: Sprache konnte nicht erkannt werden",
        "err_already": "{name}: das Dokument ist bereits auf {lang}",
        "err_no_model": "{name}: kein Modell {src} → {dst}",
        "generating": "Erzeuge {name}… Seite {done} von {total}",
        "saving": "Speichere {name}…",
        "menu_help": "&Hilfe",
        "about": "Über Argonaut…",
        "about_title": "Über Argonaut",
        "about_text": "<h3>Argonaut {version}</h3>"
                      "<p>Minimalistischer Offline-Dokumentübersetzer.</p>"
                      "<p>Die Übersetzung läuft vollständig auf deinem Rechner mit "
                      "<a href='https://www.argosopentech.com/'>Argos Translate</a> und "
                      "<a href='https://github.com/LibreTranslate/argos-translate-files'>argos-translate-files</a>; "
                      "deine Dokumente verlassen nie deinen Rechner.</p>"
                      "<p>Unterstützte Formate: {formats}</p>"
                      "<p><a href='https://github.com/Nibblex/Argonaut'>Quellcode "
                      "auf GitHub</a></p>"
                      "<p>© 2026 Sergio Rodríguez · Veröffentlicht unter der "
                      "<a href='https://choosealicense.com/licenses/gpl-3.0/'>GNU GPL v3</a>.</p>",
    },
    "it": {
        "app_title": "Argonaut — Documenti",
        "menu_language": "&Lingua",
        "detect_language": "Rileva lingua",
        "swap_tooltip": "Scambia le lingue",
        "hint": "Trascina i file qui o usa «Aggiungi…»  ·  Formati: {formats}",
        "add": "Aggiungi…",
        "remove": "Rimuovi",
        "clear": "Svuota",
        "output": "Destinazione…",
        "output_tooltip": "Scegli la cartella dove salvare le traduzioni",
        "output_default": "Accanto a ogni originale",
        "output_open_tooltip": "Apri la cartella di destinazione",
        "output_reset_tooltip": "Torna a salvare accanto a ogni originale",
        "open": "Apri",
        "open_tooltip": "Apri i file selezionati",
        "menu_engine": "Mo&tore",
        "engine_nllb": "NLLB-200 (qualità superiore)",
        "nllb_download_title": "Modello NLLB-200",
        "nllb_download_msg": "Il motore NLLB-200 richiede un download unico "
                             "di circa {size} MB. Scaricarlo ora?",
        "downloading_model": "Download del modello NLLB-200…",
        "download_failed": "Il download non è riuscito: {error}",
        "engine_status": "Motore: {name}",
        "nllb_remove": "Elimina il modello NLLB-200…",
        "nllb_remove_msg": "Il modello scaricato (~{size} MB) verrà "
                           "eliminato dal disco. Continuare?",
        "nllb_removed": "Modello NLLB-200 eliminato.",
        "ready": "Pronto.",
        "clear_status": "Pulisci",
        "clear_status_tooltip": "Pulisci il riepilogo",
        "translate": "Traduci",
        "cancel": "Annulla",
        "no_packages": "Nessun pacchetto di lingua installato. Installane uno con:\n"
                       "argospm update && argospm install translate-en_es",
        "select_documents": "Seleziona documenti",
        "documents_filter": "Documenti ({patterns})",
        "output_dir_title": "Cartella di destinazione",
        "no_files_title": "Nessun file",
        "no_files_msg": "Aggiungi almeno un documento.",
        "languages_title": "Lingue",
        "same_language": "La lingua di origine e quella di destinazione coincidono.",
        "no_model_title": "Nessun modello",
        "no_model_msg": "Nessun modello installato per tradurre da {src} a {dst}.",
        "cancelling": "Annullamento…",
        "translating": "Traduzione di {name}… (file {index} di {total})",
        "detected": "lingua rilevata: {name}",
        "cancelled": "Operazione annullata.",
        "translated_header": "Tradotti:",
        "errors_header": "Errori:",
        "err_detect": "{name}: impossibile rilevare la lingua",
        "err_already": "{name}: il documento è già in {lang}",
        "err_no_model": "{name}: nessun modello {src} → {dst}",
        "generating": "Generazione di {name}… pagina {done} di {total}",
        "saving": "Salvataggio di {name}…",
        "menu_help": "Ai&uto",
        "about": "Informazioni su Argonaut…",
        "about_title": "Informazioni su Argonaut",
        "about_text": "<h3>Argonaut {version}</h3>"
                      "<p>Traduttore di documenti minimalista e offline.</p>"
                      "<p>La traduzione avviene interamente sul tuo computer con "
                      "<a href='https://www.argosopentech.com/'>Argos Translate</a> e "
                      "<a href='https://github.com/LibreTranslate/argos-translate-files'>argos-translate-files</a>; "
                      "i tuoi documenti non lasciano mai la tua macchina.</p>"
                      "<p>Formati supportati: {formats}</p>"
                      "<p><a href='https://github.com/Nibblex/Argonaut'>Codice "
                      "sorgente su GitHub</a></p>"
                      "<p>© 2026 Sergio Rodríguez · Rilasciato sotto licenza "
                      "<a href='https://choosealicense.com/licenses/gpl-3.0/'>GNU GPL v3</a>.</p>",
    },
    "pt": {
        "app_title": "Argonaut — Documentos",
        "menu_language": "&Idioma",
        "detect_language": "Detectar idioma",
        "swap_tooltip": "Trocar os idiomas",
        "hint": "Arraste arquivos para cá ou use «Adicionar…»  ·  Formatos: {formats}",
        "add": "Adicionar…",
        "remove": "Remover",
        "clear": "Esvaziar",
        "output": "Destino…",
        "output_tooltip": "Escolher a pasta onde salvar as traduções",
        "output_default": "Junto a cada original",
        "output_open_tooltip": "Abrir a pasta de destino",
        "output_reset_tooltip": "Voltar a salvar junto a cada original",
        "open": "Abrir",
        "open_tooltip": "Abrir os arquivos selecionados",
        "menu_engine": "Mo&tor",
        "engine_nllb": "NLLB-200 (maior qualidade)",
        "nllb_download_title": "Modelo NLLB-200",
        "nllb_download_msg": "O motor NLLB-200 requer um download único de "
                             "cerca de {size} MB. Baixá-lo agora?",
        "downloading_model": "Baixando o modelo NLLB-200…",
        "download_failed": "O download falhou: {error}",
        "engine_status": "Motor: {name}",
        "nllb_remove": "Excluir o modelo NLLB-200…",
        "nllb_remove_msg": "O modelo baixado (~{size} MB) será excluído do "
                           "disco. Continuar?",
        "nllb_removed": "Modelo NLLB-200 excluído.",
        "ready": "Pronto.",
        "clear_status": "Limpar",
        "clear_status_tooltip": "Limpar o resumo",
        "translate": "Traduzir",
        "cancel": "Cancelar",
        "no_packages": "Nenhum pacote de idioma instalado. Instale um com:\n"
                       "argospm update && argospm install translate-en_es",
        "select_documents": "Selecionar documentos",
        "documents_filter": "Documentos ({patterns})",
        "output_dir_title": "Pasta de destino",
        "no_files_title": "Sem arquivos",
        "no_files_msg": "Adicione pelo menos um documento.",
        "languages_title": "Idiomas",
        "same_language": "O idioma de origem e o de destino são o mesmo.",
        "no_model_title": "Sem modelo",
        "no_model_msg": "Não há um modelo instalado para traduzir de {src} para {dst}.",
        "cancelling": "Cancelando…",
        "translating": "Traduzindo {name}… (arquivo {index} de {total})",
        "detected": "idioma detectado: {name}",
        "cancelled": "Operação cancelada.",
        "translated_header": "Traduzidos:",
        "errors_header": "Erros:",
        "err_detect": "{name}: não foi possível detectar o idioma",
        "err_already": "{name}: o documento já está em {lang}",
        "err_no_model": "{name}: não há modelo {src} → {dst}",
        "generating": "Gerando {name}… página {done} de {total}",
        "saving": "Salvando {name}…",
        "menu_help": "A&juda",
        "about": "Sobre o Argonaut…",
        "about_title": "Sobre o Argonaut",
        "about_text": "<h3>Argonaut {version}</h3>"
                      "<p>Tradutor de documentos minimalista e offline.</p>"
                      "<p>A tradução acontece inteiramente no seu computador com "
                      "<a href='https://www.argosopentech.com/'>Argos Translate</a> e "
                      "<a href='https://github.com/LibreTranslate/argos-translate-files'>argos-translate-files</a>; "
                      "seus documentos nunca saem da sua máquina.</p>"
                      "<p>Formatos suportados: {formats}</p>"
                      "<p><a href='https://github.com/Nibblex/Argonaut'>Código-fonte "
                      "no GitHub</a></p>"
                      "<p>© 2026 Sergio Rodríguez · Publicado sob a licença "
                      "<a href='https://choosealicense.com/licenses/gpl-3.0/'>GNU GPL v3</a>.</p>",
    },
}

_current = DEFAULT


def current_language():
    return _current


def load_language():
    """Loads the saved language (or the default one) at startup."""
    global _current
    code = QSettings().value("ui_language", DEFAULT)
    _current = code if code in STRINGS else DEFAULT
    return _current


def set_language(code):
    global _current
    if code in STRINGS:
        _current = code
        QSettings().setValue("ui_language", code)


def tr(key, **kwargs):
    text = STRINGS[_current].get(key) or STRINGS[DEFAULT].get(key, key)
    return text.format(**kwargs) if kwargs else text
