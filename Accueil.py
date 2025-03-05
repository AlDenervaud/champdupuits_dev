import os
import streamlit as st
import pandas as pd

from pages.utils.helper import UpdateOrder
       
# Title of the Streamlit app
st.title(":rainbow[Bienvenue au Champs du Puits]")

st.markdown("""Sur ce site vous pourrez trouver la liste des produits de la ferme Au Champ du Puits
 et créer un bon de commande à télécharger. Envoyez le bon de commande à l'adresse email ci-dessous, 
 nous tâcherons de vous répondre au plus vite!
 
 La liste est indicative uniquement et ne reflète pas l'état des stocks,
 il se peut que certains produits soient indisponibles.""")

st.markdown("### Contact")
st.markdown("GAEC Au Champ du Puits  \n211 chemin de la Fontaine  \n01430, Peyriat")

st.markdown('<a href="mailto:lechampdupuits@gmail.com">lechampdupuits@gmail.com</a>', unsafe_allow_html=True)
st.page_link("https://www.instagram.com/lechampdupuits/", label="-> Instagram <-")

