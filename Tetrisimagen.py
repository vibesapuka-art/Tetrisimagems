import streamlit as st
from PIL import Image, ImageOps, ImageFilter
import io
import time
import random

# --- CONFIGURAÇÕES TÉCNICAS (PRECISÃO 300 DPI) ---
A4_WIDTH, A4_HEIGHT = 2480, 3508
CM_TO_PX = 118.11

def tornar_impar(n):
    n = int(n)
    return n if n % 2 != 0 else n + 1

def gerar_contorno_individual(img, medida_cm, sangria_cm, linha_ativa, nivel_suavidade, espelhar):
    # Converte para RGBA e faz uma cópia para não afetar o original na memória
    img_proc = img.convert("RGBA")
    
    if espelhar:
        img_proc = ImageOps.mirror(img_proc)

    bbox = img_proc.getbbox()
    if bbox:
        img_proc = img_proc.crop(bbox)

    alvo_px = int(medida_cm * CM_TO_PX)
    w, h = img_proc.size
    proporcao = min(alvo_px / w, alvo_px / h)
    img_proc = img_proc.resize((int(w * proporcao), int(h * proporcao)), Image.LANCZOS)

    dist_px = int(sangria_cm * CM_TO_PX)
    
    if dist_px > 0:
        padding = dist_px + 20
        canvas_alpha = Image.new("L", (img_proc.width + padding*2, img_proc.height + padding*2), 0)
        canvas_alpha.paste(img_proc.split()[3], (padding, padding))
        mask = canvas_alpha.filter(ImageFilter.MaxFilter(tornar_impar(dist_px)))
        if nivel_suavidade > 0:
            mask = mask.filter(ImageFilter.GaussianBlur(radius=nivel_suavidade/2))
            mask = mask.point(lambda p: 255 if p > 128 else 0)
    else:
        mask = img_proc.split()[3].point(lambda p: 255 if p > 128 else 0)

    peca_final = Image.new("RGBA", mask.size if dist_px > 0 else img_proc.size, (0, 0, 0, 0))
    
    if linha_ativa:
        linha_mask = mask.filter(ImageFilter.MaxFilter(3)) if dist_px > 0 else mask
        peca_final.paste((0, 0, 0, 255), (0, 0), linha_mask)
    
    peca_final.paste((255, 255, 255, 255), (0, 0), mask)
    
    if dist_px > 0:
        off_x = (peca_final.width - img_proc.width) // 2
        off_y = (peca_final.height - img_proc.height) // 2
        peca_final.paste(img_proc, (off_x, off_y), img_proc)
    else:
        peca_final.paste(img_proc, (0, 0), img_proc)
    
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
                x, y, h_linha = m_px, y + h_linha + e_px, 0
            if y + ph <= A4_HEIGHT - m_px:
                folha.paste(p, (x, y), p)
                x, h_linha = x + pw + e_px, max(h_linha, ph)
                inseridos.append(i)
            else: break
        if not inseridos: break
        for idx in sorted(inseridos, reverse=True): lista_pendente.pop(idx)
        
        f_branca = Image.new("RGB", (A4_WIDTH, A4_HEIGHT), (255, 255, 255))
        f_branca.paste(folha, (0, 0), folha)
        folhas.append(f_branca)
    return folhas

# --- INTERFACE ---
st.set_page_config(page_title="Bazzott Studio Otimizado", layout="wide")

if 'galeria' not in st.session_state:
    st.session_state.galeria = []

with st.sidebar:
    st.title("🎨 Bazzott Editor")
    margem = st.slider("Margem (cm)", 0.3, 1.5, 0.5)
    suave = st.slider("Suavização", 0, 30, 15)
    
    st.divider()
    if st.button("🗑️ Limpar Galeria"):
        st.session_state.galeria = []
        st.rerun()

    st.divider()
    st.subheader("🪄 Ajuste em Massa")
    b_tam = st.number_input("Tamanho (cm)", 1.0, 25.0, 4.0)
    b_qtd = st.number_input("Quantidade", 1, 500, 10)
    b_san = st.slider("Sangria (cm)", 0.0, 1.0, 0.25, step=0.05)
    b_esp = st.checkbox("Espelhar Tudo", False)
    
    if st.button("🚀 Aplicar em Tudo"):
        for item in st.session_state.galeria:
            id_it = item['id']
            st.session_state[f"m{id_it}"] = b_tam
            st.session_state[f"q{id_it}"] = b_qtd
            st.session_state[f"s{id_it}"] = b_san
            st.session_state[f"e{id_it}"] = b_esp
        st.rerun()

u = st.file_uploader("Adicione seus PNGs", type="png", accept_multiple_files=True)
if u:
    for f in u:
        # Verifica se já não adicionamos este arquivo específico nesta rodada
        id_novo = f"img_{f.name}_{time.time()}_{random.randint(0,999)}"
        st.session_state.galeria.append({
            "id": id_novo,
            "name": f.name,
            "img": Image.open(f).convert("RGBA")
        })
    st.rerun()

if st.session_state.galeria:
    pecas_pdf = []
    total_unidades = 0
    remover_id = None

    for i, item in enumerate(st.session_state.galeria):
        id_it = item['id']
        with st.expander(f"📦 {item['name']}", expanded=True):
            col_del, col_img, col_cfg1, col_cfg2 = st.columns([0.1, 0.5, 2, 2])
            
            with col_del:
                if st.button("❌", key=f"btn_del_{id_it}"):
                    remover_id = i
            
            with col_img:
                st.image(item['img'], use_container_width=True)
            
            with col_cfg1:
                # Inicialização de valores
                if f"m{id_it}" not in st.session_state: st.session_state[f"m{id_it}"] = 4.0
                if f"q{id_it}" not in st.session_state: st.session_state[f"q{id_it}"] = 1
                
                t = st.number_input("Tam (cm)", 1.0, 25.0, key=f"m{id_it}")
                q = st.number_input("Qtd (un)", 1, 500, key=f"q{id_it}")
            
            with col_cfg2:
                if f"s{id_it}" not in st.session_state: st.session_state[f"s{id_it}"] = 0.25
                if f"e{id_it}" not in st.session_state: st.session_state[f"e{id_it}"] = False
                
                s = st.slider("Sangria", 0.0, 1.0, key=f"s{id_it}", step=0.05)
                l = st.checkbox("Linha Corte", True, key=f"l{id_it}")
                e = st.checkbox("Espelhar", key=f"e{id_it}")

            # Prepara as figuras para o PDF
            p_final = gerar_contorno_individual(item['img'], t, s, l, suave, e)
            for _ in range(int(q)):
                pecas_pdf.append(p_final)
                total_unidades += 1

    if remover_id is not None:
        st.session_state.galeria.pop(remover_id)
        st.rerun()

    st.sidebar.info(f"Total de figuras: {total_unidades}")

    if st.button(f"🎨 GERAR PDF ({total_unidades} FIGURAS)", use_container_width=True):
        if pecas_pdf:
            with st.spinner("Montando as páginas..."):
                folhas = montar_folhas(pecas_pdf, margem)
                if folhas:
                    st.subheader("🖼️ Pré-visualização")
                    for idx, folha in enumerate(folhas):
                        st.image(folha, caption=f"Página {idx+1}", use_container_width=True)
                    
                    output = io.BytesIO()
                    folhas[0].save(output, format="PDF", save_all=True, append_images=folhas[1:], resolution=300.0)
                    st.download_button("📥 Baixar PDF", output.getvalue(), "Bazzott_Final.pdf", use_container_width=True)
