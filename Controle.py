import streamlit as st
import cv2
import face_recognition
import numpy as np
import time
import os
from geopy.distance import geodesic
from streamlit_javascript import st_javascript
import pandas as pd
from datetime import datetime

# Créer dossier pour stocker les photos si inexistant
if not os.path.exists("photos"):
    os.makedirs("photos")

# Fichier journal
log_path = "journal_presence.csv"

st.set_page_config(page_title="Contrôle de Présence", layout="centered")
st.title("📍 Application de Contrôle de Présence")

menu = ["📷 Enregistrement", "✅ Vérification", "📊 Journal de Présence"]
choice = st.sidebar.radio("Navigation", menu)

if "base_location" not in st.session_state:
    st.session_state.base_location = None

def get_real_location():
    coords = st_javascript("""
        navigator.geolocation.getCurrentPosition(
            (pos) => {
                const lat = pos.coords.latitude;
                const lon = pos.coords.longitude;
                Streamlit.setComponentValue([lat, lon]);
            },
            (err) => {
                Streamlit.setComponentValue(null);
            }
        );
    """)
    return tuple(coords) if coords else None

def capture_image():
    cap = cv2.VideoCapture(0)
    time.sleep(1)
    ret, frame = cap.read()
    cap.release()
    if ret:
        return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    return None

def dessiner_visages(image_rgb):
    face_locations = face_recognition.face_locations(image_rgb)
    image_bgr = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR)
    for top, right, bottom, left in face_locations:
        cv2.rectangle(image_bgr, (left, top), (right, bottom), (0, 255, 0), 2)
    return cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)

def enregistrer_presence(tel, location, distance, status):
    log_data = {
        "Telephone": tel,
        "DateHeure": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Latitude": location[0],
        "Longitude": location[1],
        "Distance_m": int(distance),
        "Statut": status
    }
    df = pd.DataFrame([log_data])
    if not os.path.exists(log_path):
        df.to_csv(log_path, index=False)
    else:
        df.to_csv(log_path, mode='a', header=False, index=False)

# 📷 ENREGISTREMENT
if choice == "📷 Enregistrement":
    st.subheader("Étape 1 : Enregistrement de l'agent")
    tel = st.text_input("Numéro de téléphone de l'agent", max_chars=8)

    if len(tel) == 8 and tel.isdigit():
        location = get_real_location()
        if location:
            st.success(f"📌 Coordonnées détectées automatiquement : {location}")
            st.session_state.base_location = location
        else:
            st.warning("⚠️ GPS indisponible. Entrez manuellement :")
            lat = st.number_input("Latitude manuelle", value=6.1319, format="%.6f")
            lon = st.number_input("Longitude manuelle", value=1.2228, format="%.6f")
            location = (lat, lon)
            st.session_state.base_location = location

        if st.button("📸 Capturer et Enregistrer"):
            img = capture_image()
            if img is not None:
                cv2.imwrite(f"photos/{tel}.jpg", cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
                st.image(dessiner_visages(img), caption="Image avec détection de visage", use_container_width=True)
                st.success("✅ Agent enregistré avec succès.")
                st.info(f"Coordonnées de référence : {location}")
            else:
                st.error("Erreur de capture.")
    else:
        st.warning("Numéro invalide (8 chiffres).")

# ✅ VÉRIFICATION
elif choice == "✅ Vérification":
    st.subheader("Étape 2 : Vérification de la présence")
    tel = st.text_input("Numéro de téléphone de l'agent", max_chars=8)

    if len(tel) == 8 and tel.isdigit():
        path = f"photos/{tel}.jpg"
        if not os.path.exists(path):
            st.error("❌ Aucun enregistrement pour ce numéro.")
        else:
            location = get_real_location()
            if location:
                st.success(f"📌 Position actuelle : {location}")
            else:
                st.warning("⚠️ GPS indisponible. Entrez manuellement :")
                lat = st.number_input("Latitude actuelle", value=6.1319, format="%.6f")
                lon = st.number_input("Longitude actuelle", value=1.2228, format="%.6f")
                location = (lat, lon)

            if st.button("📸 Vérifier la Présence") and location:
                ref_img = face_recognition.load_image_file(path)
                ref_enc = face_recognition.face_encodings(ref_img)

                new_img = capture_image()
                if new_img is not None:
                    new_enc = face_recognition.face_encodings(new_img)

                    if ref_enc and new_enc:
                        match = face_recognition.compare_faces([ref_enc[0]], new_enc[0], tolerance=0.3)[0]
                        distance = geodesic(st.session_state.base_location, location).meters
                        st.image(dessiner_visages(new_img), caption="Image capturée avec détection de visage", use_container_width=True)

                        if match:
                            if distance <= 100:
                                st.success(f"✅ Agent reconnu à {int(distance)} m : Présence validée.")
                                enregistrer_presence(tel, location, distance, "Validée")
                            else:
                                st.error(f"❌ Trop éloigné : {int(distance)} m > 100 m.")
                                enregistrer_presence(tel, location, distance, "Refusée - Trop éloigné")
                        else:
                            st.error("❌ Visage non reconnu.")
                            enregistrer_presence(tel, location, 0, "Refusée - Visage non reconnu")
                    else:
                        st.error("⚠️ Visage non détecté.")
                else:
                    st.error("Erreur de webcam.")
    else:
        st.warning("Numéro invalide (8 chiffres).")

# 📊 JOURNAL DE PRÉSENCE
elif choice == "📊 Journal de Présence":
    st.subheader("📊 Journal de Présence des Agents")
    if os.path.exists(log_path):
        df = pd.read_csv(log_path)

        # Filtrage par téléphone
        unique_tels = df["Telephone"].unique().tolist()
        tel_filter = st.selectbox("Filtrer par numéro de téléphone", ["Tous"] + unique_tels)

        if tel_filter != "Tous":
            df = df[df["Telephone"] == tel_filter]

        st.dataframe(df, use_container_width=True)

        # Bouton de téléchargement
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📤 Télécharger le journal CSV",
            data=csv,
            file_name="journal_presence.csv",
            mime="text/csv"
        )
    else:
        st.info("Aucune donnée de présence enregistrée pour l’instant.")
