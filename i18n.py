"""UI text for marbleness, Italian and English. Plain dict lookup, no
framework, nothing translated here reaches the results sheet, curator_id,
image_id and the suggested-id word lists are never translated.
"""

import streamlit as st

LANGUAGES = {"it": "Italiano", "en": "English"}
DEFAULT_LANGUAGE = "it"

_STRINGS = {
    "it": {
        "consent_header": "Prima di iniziare",
        "consent_intro": (
            "Grazie per aiutarci in questa valutazione.\n\n"
            "Per ogni foto, usa il cursore per stimare quanto, secondo te, il pesce si avvicina a uno "
            "di questi due estremi:\n\n"
            "- **0.0**, trota fario atlantica pura (trota fario)\n"
            "- **1.0**, trota marmorata pura (trota marmorata)\n\n"
            "Usa l'intera scala, compreso il centro, se lo ritieni corretto. "
            "Vedrai {total_items} immagini distribuite uniformemente lungo l'intera "
            "scala.\n\n"
            "Ti chiediamo di dare una risposta per ogni foto, anche se è una stima. "
            "Se non sei sicuro/a del tuo giudizio, seleziona **\"Bassa confidenza\"** "
            "per indicarlo: non serve a saltare la foto."
        ),
        "consent_data_header": "Dati e consenso",
        "consent_summary": (
            "Conserviamo le tue valutazioni, con un ID a te assegnato, per valutare "
            "quanto un modello di machine learning si avvicini al giudizio umano. "
            "Non raccogliamo altro: nessun indirizzo IP, nessuna posizione, nessuna "
            "informazione su browser/dispositivo, nessun nome o email."
        ),
        "consent_read_full_button": "📄 Leggi la dichiarazione completa",
        "consent_agree_checkbox": "Ho letto e accetto quanto sopra.",
        "consent_agree_button": "Accetto, inizia",
        "consent_dialog_close_button": "Chiudi",
        "consent_full_collect": (
            "### Cosa raccogliamo\n"
            "- L'ID assegnato all'avvio (non collegato al tuo nome o altro).\n"
            "- La tua stima per ogni foto (valore numerico da 0 a 1) e il livello di confidenza che indichi.\n"
            "- Quanto tempo resta a schermo ogni foto prima che tu proceda.\n"
            "- Un timestamp per ogni risposta."
        ),
        "consent_full_not_collect": (
            "### Cosa NON raccogliamo\n"
            "- Nessun indirizzo IP, dispositivo, browser o posizione geografica.\n"
            "- Nessun cookie o tracciamento oltre a mantenere il tuo avanzamento nel sondaggio.\n"
            "- Nessun nome, email o altra informazione identificativa."
        ),
        "consent_full_usage": (
            "### Come vengono usati i tuoi dati\n"
            "- Le tue valutazioni, insieme a quelle degli altri curatori, servono a "
            "valutare quanto le previsioni di un modello di machine learning si "
            "avvicinino al giudizio umano. Non vengono usate per addestrare quel modello.\n"
            "- Usate solo per questo progetto di ricerca, mai vendute, condivise con "
            "terzi o utilizzate al di fuori di questo progetto."
        ),
        "consent_full_id": (
            "### Il tuo ID\n"
            "- Ti viene assegnato un ID casuale (es. `clever_trout_42`) all'avvio; "
            "non è collegato al tuo nome o altro. Conservalo: ti servirà per "
            "riprendere se ti interrompi a metà. Una volta completate tutte le foto "
            "con un ID, quell'ID è concluso, un secondo giro richiede un nuovo ID assegnato."
        ),
        "consent_full_voluntary": (
            "### La partecipazione è volontaria\n"
            "- Puoi interromperti in qualsiasi momento chiudendo la scheda. Quanto "
            "già inviato resta registrato; non viene raccolto nient'altro dopo che te ne vai."
        ),
        "identify_header": "Chi sei?",
        "identify_new_subheader": "Prima volta qui?",
        "identify_new_caption": (
            "Ti assegniamo un ID unico, non puoi sceglierlo tu. Conservalo: ti "
            "servirà per riprendere se ti interrompi a metà."
        ),
        "identify_new_button": "🔀 Nuovo",
        "identify_new_button_help": "Ottieni un ID assegnato diverso",
        "identify_start_button": "Inizia con questo ID",
        "identify_resume_subheader": "Hai già iniziato?",
        "identify_resume_input_label": "Inserisci il tuo ID assegnato per riprendere",
        "identify_resume_button": "Riprendi",
        "identify_resume_warning_empty": "Inserisci prima un ID.",
        "identify_resume_error_unknown": (
            "Questo ID non esiste o ha già terminato. Inizia una nuova sessione "
            "con un ID appena assegnato qui sopra."
        ),
        "evaluate_progress_caption": "Immagine {n} di {total}, {percent}% completato",
        "evaluate_slider_label": "0 = fario pura · 1 = marmorata pura",
        "evaluate_unsure_checkbox": "Bassa confidenza",
        "evaluate_touch_hint": "Muovi il cursore per dare la tua stima, poi continua.",
        "evaluate_next_button": "Avanti",
        "complete_header": "Fatto, grazie!",
        "complete_body": "Le tue valutazioni sono state registrate. Puoi chiudere questa scheda.",
    },
    "en": {
        "consent_header": "Before you begin",
        "consent_intro": (
            "Thank you for helping evaluate trout photographs.\n\n"
            "For each photo, estimate on a slider how the fish looks between two\n"
            "extremes:\n\n"
            "- **0.0**, pure Atlantic **fario** (brown trout)\n"
            "- **1.0**, pure marble trout **marmorata**\n\n"
            "Please use the whole scale, including the middle, if that's genuinely your "
            "judgement. You will be seeing {total_items} images uniformly distributed "
            "across the entire scale.\n\n"
            "Please give an answer for every photo, even if it's a guess. If you're not "
            "confident in your judgement, tick **\"Low confidence\"** to say so. It's "
            "not a way to skip the photo."
        ),
        "consent_data_header": "Data & consent",
        "consent_summary": (
            "We store your ratings, under an ID assigned to you, to evaluate how "
            "well a machine-learning model matches human judgment. We don't collect "
            "anything else: no IP address, no location, no browser/device info, no "
            "name or email."
        ),
        "consent_read_full_button": "📄 Read the full statement",
        "consent_agree_checkbox": "I have read and agree to the statement above.",
        "consent_agree_button": "I agree, begin",
        "consent_dialog_close_button": "Close",
        "consent_full_collect": (
            "### What we collect\n"
            "- The ID assigned to you when you start (not linked to your name or anything else).\n"
            "- Your estimate for each photo (the 0-1 slider position) and the confidence level you indicate.\n"
            "- How long each photo stays on screen before you move on.\n"
            "- A timestamp for each response."
        ),
        "consent_full_not_collect": (
            "### What we do NOT collect\n"
            "- No IP address, device, browser, or geographic location.\n"
            "- No cookies or tracking beyond keeping your place in the survey.\n"
            "- No name, email, or other identifying information."
        ),
        "consent_full_usage": (
            "### How your data is used\n"
            "- Your ratings, together with other curators', are used to evaluate how "
            "closely a machine-learning model's predictions match human judgment. "
            "They are not used to train that model.\n"
            "- Used only for this research project, never sold, shared with third "
            "parties, or repurposed beyond this project."
        ),
        "consent_full_id": (
            "### About your ID\n"
            "- You're assigned a random ID (e.g. `clever_trout_42`) when you start; it "
            "isn't linked to your name or anything else. Keep note of it, you'll need "
            "it to resume if you leave partway through. Once you finish all photos "
            "under an ID, that ID is done, a repeat pass needs a freshly assigned one."
        ),
        "consent_full_voluntary": (
            "### Participation is voluntary\n"
            "- You can stop at any time by closing the tab. Anything already submitted "
            "stays recorded; nothing further is collected after you leave."
        ),
        "identify_header": "Who are you?",
        "identify_new_subheader": "New here?",
        "identify_new_caption": (
            "We assign you a unique ID, you can't pick your own. Keep note of "
            "it: you'll need it to resume if you leave partway through."
        ),
        "identify_new_button": "🔀 New",
        "identify_new_button_help": "Get a different assigned ID",
        "identify_start_button": "Start with this ID",
        "identify_resume_subheader": "Already started?",
        "identify_resume_input_label": "Enter your assigned ID to resume",
        "identify_resume_button": "Resume",
        "identify_resume_warning_empty": "Enter an ID first.",
        "identify_resume_error_unknown": (
            "That ID doesn't exist or has already finished. "
            "Start a new session with a freshly assigned ID above."
        ),
        "evaluate_progress_caption": "Image {n} of {total}, {percent}% complete",
        "evaluate_slider_label": "0 = pure fario · 1 = pure marmorata",
        "evaluate_unsure_checkbox": "Low confidence",
        "evaluate_touch_hint": "Move the slider to give your estimate, then continue.",
        "evaluate_next_button": "Next",
        "complete_header": "All done, thank you!",
        "complete_body": "Your ratings have been recorded. You can safely close this tab.",
    },
}


def t(key: str, lang: str | None = None, **kwargs) -> str:
    """Look up `key` in `lang` (or the live st.session_state.lang if `lang`
    is omitted, falling back to DEFAULT_LANGUAGE), then .format(**kwargs).

    The explicit `lang` param keeps this testable outside a running
    Streamlit session (t("key", lang="it")); call sites inside app.py just
    say t("key") and it picks up the current session's language.
    """
    if lang is None:
        lang = st.session_state.get("lang", DEFAULT_LANGUAGE)
    template = _STRINGS.get(lang, _STRINGS[DEFAULT_LANGUAGE]).get(
        key, _STRINGS[DEFAULT_LANGUAGE][key]
    )
    return template.format(**kwargs) if kwargs else template
