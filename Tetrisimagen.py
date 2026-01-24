import streamlit as st
from PIL import Image, ImageChops, ImageFilter
import io
import time
import random

# --- CONFIGURAÇÕES TÉCNICAS (PRECISÃO 300 DPI) ---
A4_WIDTH, A4_HEIGHT = 2480, 3508
CM_TO_PX = 118.11 

def tornar_impar(n):
    n = int(n)
    return n if n % 2 != 0 else n + 1

def gerar_contorno_individual(img, medida_cm, sangria_cm, linha_ativa, nivel_suavidade):
    img = img.convert("RGBA")
    bbox_limpeza = img.getbbox()
    if bbox_limpeza:
        img = img.crop(bbox_limpeza)

    alvo_px = int(medida_cm * CM_TO_PX)
    w, h = img.size
    proporcao = min(alvo_px / w, alvo_px / h)
    img = img.resize((int(w * proporcao), int(h * proporcao)), Image.LANCZOS)

    dist_px = int(sangria_cm * CM_TO_PX)
    
    if dist_px > 0:
        padding = dist_px + 20
        canvas_alpha = Image.new("L", (img.width + padding*2, img.height + padding*2), 0)
        canvas_alpha.paste(img.split()[3], (padding, padding))
        mask = canvas_alpha.filter(ImageFilter.MaxFilter(tornar_impar(dist_px)))
        if nivel_suavidade > 0:
            mask = mask.filter(ImageFilter.GaussianBlur(radius=nivel_suavidade/2))
            mask = mask.point(lambda p: 255 if p > 128 else 0)
    else:
        mask = img.split()[3].point(lambda p: 255 if p > 128 else 0)

    peca_final = Image.new("RGBA", mask.size if dist_px > 0 else img.size, (0, 0, 0, 0))
    
    if linha_ativa:
        linha_mask = mask.filter(ImageFilter.MaxFilter(3)) if dist_px > 0 else mask
        peca_final.paste((0, 0, 0, 255), (0, 0), linha_mask)
    
    peca_final.paste((255, 255, 255, 255), (0, 0), mask)
    
    if dist_px > 0:
        off_x = (peca_final.width - img.width) // 2
        off_y = (peca_final.height - img.height) // 2
        peca_final.paste(img, (off_x, off_y), img)
    else:
        peca_final.paste(img, (0, 0), img)
    
    return peca_final.crop(peca_final.getbbox())

def montar_folhas(pecas, margem_cm):
    m_px = int(margem_cm * CM_TO_PX)
    e_px = int(0.1 * CM_TO_PX) 
    folhas = []
    lista_pendente = pecas.copy()
    
    while lista_pendente:
        folha = Image.new("RGBA", (A4_WIDTH, A4_HEIGHT), (0,0,0,0))
        x, y, h_linha = m_px, m_px, 0
        inseridos = []
        for i, p in enumerate(lista_pendente):
            pw, ph = p.size
            if x + pw > A4_WIDTH - m_px:
                x = m_px
                y += h_linha + e_px
                h_linha = 0
            if y + ph <= A4_HEIGHT - m_px:
                folha.paste(p, (x, y), p)
                x += pw + e_px
                h_linha = max(h_linha, ph)
                inseridos.append(i)
            else: break
        if not inseridos: break
        for idx in sorted(inseridos, reverse=True): lista_pendente.pop(idx)
        f_branca = Image.new("RGB", (A4_WIDTH, A4_HEIGHT), (255, 255, 255))
        f_branca.paste(folha, (0, 0), folha)
        folhas.append(f_branca)
    return folhas

# --- INTERFACE ---
st.set_page_config(page_title="Bazzott Lov´s Studio", layout="wide")

if 'galeria' not in st.session_state:
    st.session_state.galeria = []

with st.sidebar:
    st.title("🛠️ Painel de Controle")
    # CORREÇÃO: Removido width="stretch" que causava TypeError
    if st.button("🗑️ LIMPAR TUDO", key="btn_limpar_total", use_container_width=True):
        st.session_state.galeria = []
        st.rerun()

    st.divider()
    st.header("⚙️ Configurações")
    margem = st.slider("Margem da Folha (cm)", 0.3, 1.5, 0.5)
    suave = st.slider("Suavização", 0, 30, 15)
    
    st.divider()
    st.header("🪄 Ajuste em Massa")
    b_tam = st.number_input("Tam Geral (cm)", 1.0, 25.0, 4.0)
    b_qtd = st.number_input("Qtd Geral", 1, 500, 20)
    b_san = st.slider("Sangria Geral (cm)", 0.0, 1.0, 0.25, step=0.05)
    
    if st.button("Aplicar a Todos", key="btn_massa", use_container_width=True):
        for item in st.session_state.galeria:
            iid = item['id']
            st.session_state[f"m_{iid}"] = b_tam
            st.session_state[f"q_{iid}"] = b_qtd
            st.session_state[f"s_{iid}"] = b_san
        st.rerun()

u = st.file_uploader("Suba seus PNGs", type="png", accept_multiple_files=True, key="uploader_main")
if u:
    for f in u:
        if f.name not in [img['name'] for img in st.session_state.galeria]:
            unique_id = f"{int(time.time())}_{random.randint(0, 1000)}"
            st.session_state.galeria.append({
                "id": unique_id, 
                "name": f.name, 
                "img": Image.open(f).copy()
            })
    st.rerun()

if st.session_state.galeria:
    pecas_preparadas = []
    total_figuras = 0
    indices_remover = []

    for i, item in enumerate(st.session_state.galeria):
        iid = item['id']
        with st.expander(f"📦 Configurar: {item['name']}", expanded=True):
            c_del, c1, c2, c3 = st.columns([0.1, 0.9, 2, 2])
            
            with c_del:
                if st.button("❌", key=f"del_btn_{iid}"): 
                    indices_remover.append(i)
            
            with c1: 
                # Para imagens, width='stretch' é aceito em versões novas ou use_container_width nas antigas
                st.image(item['img'], width=80)
            
            with c2:
                t = st.number_input("cm", 1.0, 25.0, key=f"m_{iid}", value=st.session_state.get(f"m_{iid}", 4.0))
                q = st.number_input("un", 1, 500, key=f"q_{iid}", value=st.session_state.get(f"q_{iid}", 10))
            
            with c3:
                s = st.slider("Sangria", 0.0, 1.0, key=f"s_{iid}", value=st.session_state.get(f"s_{iid}", 0.25), step=0.05)
                l = st.checkbox("Linha de Corte", True, key=f"l_{iid}")
            
            p = gerar_contorno_individual(item['img'], t, s, l, suave)
            for _ in range(q): 
                pecas_preparadas.append(p)
                total_figuras += 1

    if indices_remover:
        for idx in sorted(indices_remover, reverse=True): 
            st.session_state.galeria.pop(idx)
        st.rerun()

    if st.button(f"🚀 GERAR E VISUALIZAR ({total_figuras} figuras)", key="btn_gerar_final", use_container_width=True):
        folhas = montar_folhas(pecas_preparadas, margem)
        if folhas:
            st.subheader("🖼️ Pré-visualização")
            for idx, f in enumerate(folhas):
                st.image(f, caption=f"Página {idx+1}", use_container_width=True)
            
            pdf_bytes = io.BytesIO()
            folhas[0].save(pdf_bytes, format="PDF", save_all=True, append_images=folhas[1:], resolution=300.0)
            st.divider()
            st.download_button("📥 BAIXAR PDF FINAL", pdf_bytes.getvalue(), "Studio_Final.pdf", key="btn_download_final", use_container_width=True)
