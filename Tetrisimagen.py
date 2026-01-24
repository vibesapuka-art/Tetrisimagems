import streamlit as st
from PIL import Image, ImageChops, ImageFilter
import io

# --- CONFIGURAÇÕES TÉCNICAS (PRECISÃO 300 DPI) ---
A4_WIDTH, A4_HEIGHT = 2480, 3508
CM_TO_PX = 118.11 

def tornar_impar(n):
    n = int(n)
    return n if n % 2 != 0 else n + 1

def gerar_contorno_individual(img, medida_cm, sangria_cm, linha_ativa, nivel_suavidade):
    bbox_limpeza = img.getbbox()
    if bbox_limpeza:
        img = img.crop(bbox_limpeza)

    alvo_px = int(medida_cm * CM_TO_PX)
    w, h = img.size
    proporcao = min(alvo_px / w, alvo_px / h)
    img = img.resize((int(w * proporcao), int(h * proporcao)), Image.LANCZOS).convert("RGBA")

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
            else:
                break
        
        if not inseridos: break
        for idx in sorted(inseridos, reverse=True): lista_pendente.pop(idx)
        
        f_branca = Image.new("RGB", (A4_WIDTH, A4_HEIGHT), (255, 255, 255))
        f_branca.paste(folha, (0, 0), folha)
        folhas.append(f_branca)
        
    return folhas

# --- INTERFACE ---
st.set_page_config(page_title="Bazzott Lov´s Editor", layout="wide")

if 'galeria' not in st.session_state:
    st.session_state.galeria = []

with st.sidebar:
    st.header("⚙️ Ajustes de Margem")
    margem = st.slider("Margem da Folha (cm)", 0.3, 1.5, 0.5, help="Diminua para encaixar mais figuras nas bordas.")
    suave = st.slider("Suavização", 0, 30, 15)
    
    st.divider()
    st.header("🪄 Ajuste em Massa")
    b_tam = st.number_input("Tam (cm)", 1.0, 25.0, 4.0)
    b_qtd = st.number_input("Qtd", 1, 500, 20)
    b_san = st.slider("Sangria (cm)", 0.0, 1.0, 0.25, step=0.05)
    
    if st.button("Aplicar a Todos"):
        for i in range(len(st.session_state.galeria)):
            st.session_state[f"m{i}"] = b_tam
            st.session_state[f"q{i}"] = b_qtd
            st.session_state[f"s{i}"] = b_san
        st.rerun()

u = st.file_uploader("Subir PNGs", type="png", accept_multiple_files=True)
if u:
    for f in u:
        if f.name not in [img['name'] for img in st.session_state.galeria]:
            st.session_state.galeria.append({"name": f.name, "img": Image.open(f).copy()})

if st.session_state.galeria:
    pecas_preparadas = []
    total_figuras = 0
    indices_remover = []

    for i, item in enumerate(st.session_state.galeria):
        with st.expander(f"Configurar: {item['name']}", expanded=True):
            c_del, c1, c2, c3 = st.columns([0.1, 0.9, 2, 2])
            with c_del:
                if st.button("❌", key=f"del_{i}"): indices_remover.append(i)
            with c1: st.image(item['img'], width=60)
            with c2:
                t = st.number_input("cm", 1.0, 25.0, key=f"m{i}", value=st.session_state.get(f"m{i}", 4.0))
                q = st.number_input("un", 1, 500, key=f"q{i}", value=st.session_state.get(f"q{i}", 10))
            with c3:
                s = st.slider("Sang", 0.0, 1.0, key=f"s{i}", value=st.session_state.get(f"s{i}", 0.25), step=0.05)
                l = st.checkbox("Corte", True, key=f"l{i}")
            
            p = gerar_contorno_individual(item['img'], t, s, l, suave)
            for _ in range(q): 
                pecas_preparadas.append(p)
                total_figuras += 1

    if indices_remover:
        for idx in sorted(indices_remover, reverse=True): st.session_state.galeria.pop(idx)
        st.rerun()

    if st.button(f"🚀 GERAR E VISUALIZAR ({total_figuras} figuras)", use_container_width=True):
        folhas = montar_folhas(pecas_preparadas, margem)
        if folhas:
            st.subheader("🖼️ Pré-visualização das Páginas")
            # Mostra as imagens na tela antes do botão de download 
            for idx, f in enumerate(folhas):
                st.image(f, caption=f"Página {idx+1} - Verifique o encaixe nas bordas", use_container_width=True)
            
            pdf_bytes = io.BytesIO()
            folhas[0].save(pdf_bytes, format="PDF", save_all=True, append_images=folhas[1:], resolution=300.0)
            
            st.divider()
            st.download_button("📥 BAIXAR PDF FINAL", pdf_bytes.getvalue(), "Bazzott_Lovs_Editor.pdf", use_container_width=True)
