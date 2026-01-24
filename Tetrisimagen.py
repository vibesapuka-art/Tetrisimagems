import streamlit as st
from PIL import Image, ImageChops, ImageFilter
import io
import random

# --- CONFIGURAÇÕES TÉCNICAS (PRECISÃO 300 DPI) ---
A4_WIDTH, A4_HEIGHT = 2480, 3508
CM_TO_PX = 118.11 

def tornar_impar(n):
    n = int(n)
    return n if n % 2 != 0 else n + 1

# --- MOTOR DE CONTORNO ---
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
        padding = dist_px + 40
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

# --- MONTAGEM DA FOLHA ---
def montar_folhas(pecas, margem_cm):
    m_px = int(margem_cm * CM_TO_PX)
    e_px = int(0.15 * CM_TO_PX) 
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
        
        bbox = folha.getbbox()
        f_branca = Image.new("RGB", (A4_WIDTH, A4_HEIGHT), (255, 255, 255))
        if bbox:
            w_c, h_c = bbox[2]-bbox[0], bbox[3]-bbox[1]
            off_x, off_y = (A4_WIDTH - w_c)//2 - bbox[0], (A4_HEIGHT - h_c)//2 - bbox[1]
            f_branca.paste(folha, (off_x, off_y), folha)
        folhas.append(f_branca)
    return folhas

# --- INTERFACE ---
st.set_page_config(page_title="Bazzott Lov´s Studio Pro", layout="wide")

# Inicializa a galeria se não existir
if 'galeria' not in st.session_state:
    st.session_state.galeria = []

with st.sidebar:
    st.header("⚙️ Configurações Globais")
    margem = st.slider("Margem da Folha (cm)", 0.5, 2.0, 1.0)
    suave = st.slider("Suavização do Corte", 0, 30, 15)
    
    st.divider()
    st.header("🪄 Sincronização em Massa")
    b_tam = st.number_input("Tamanho do Desenho (cm)", 1.0, 25.0, 4.0)
    b_qtd = st.number_input("Quantidade Total", 1, 500, 20)
    b_san = st.slider("Sangria Padrão (cm)", 0.0, 1.0, 0.25, step=0.05)
    
    if st.button("Aplicar a Todas as Imagens da Galeria"):
        for i in range(len(st.session_state.galeria)):
            st.session_state[f"m{i}"] = b_tam
            st.session_state[f"q{i}"] = b_qtd
            st.session_state[f"s{i}"] = b_san
        st.rerun()

# Uploader que alimenta a galeria persistente
u = st.file_uploader("Adicionar novos PNGs", type="png", accept_multiple_files=True)
if u:
    for f in u:
        # Só adiciona se o nome não estiver na galeria para não duplicar no upload
        if f.name not in [item['name'] for item in st.session_state.galeria]:
            # Guardamos os bytes da imagem para que não sumam
            img_data = Image.open(f).copy()
            st.session_state.galeria.append({"name": f.name, "img": img_data})

if st.session_state.galeria:
    pecas_para_pdf = []
    total_figuras = 0
    indices_para_remover = []

    # Exibição da Galeria
    for i, item in enumerate(st.session_state.galeria):
        # Criamos um container para cada item para colocar o botão X no topo
        with st.expander(f"🖼️ {item['name']}", expanded=True):
            col_txt, col_del = st.columns([0.9, 0.1])
            with col_del:
                if st.button("❌", key=f"del_{i}"):
                    indices_para_remover.append(i)
            
            c1, c2, c3 = st.columns([1, 2, 2])
            with c1: st.image(item['img'], width=80)
            with c2:
                t = st.number_input("Tam (cm)", 1.0, 25.0, key=f"m{i}", value=st.session_state.get(f"m{i}", 4.0))
                q = st.number_input("Qtd", 1, 500, key=f"q{i}", value=st.session_state.get(f"q{i}", 10))
            with c3:
                s = st.slider("Sangria (cm)", 0.0, 1.0, key=f"s{i}", value=st.session_state.get(f"s{i}", 0.25), step=0.05)
                l = st.checkbox("Linha Corte", True, key=f"l{i}")
            
            p_processada = gerar_contorno_individual(item['img'], t, s, l, suave)
            for _ in range(q): 
                pecas_para_pdf.append(p_processada)
                total_figuras += 1

    # Processar remoções fora do loop de interface
    if indices_para_remover:
        for idx in sorted(indices_para_remover, reverse=True):
            st.session_state.galeria.pop(idx)
            # Limpa chaves de estado relacionadas
            for k in [f"m{idx}", f"q{idx}", f"s{idx}", f"l{idx}"]:
                if k in st.session_state: del st.session_state[k]
        st.rerun()

    st.sidebar.markdown(f"### 📊 Resumo")
    st.sidebar.info(f"Total: **{total_figuras}** figuras")

    if st.button(f"🚀 GERAR PDF COM {total_figuras} FIGURAS", use_container_width=True):
        folhas_finais = montar_folhas(pecas_para_pdf, margem)
        if folhas_finais:
            st.success(f"✅ PDF Gerado com {total_figuras} figuras!")
            for idx, f in enumerate(folhas_finais): st.image(f, caption=f"Página {idx+1}")
            pdf_output = io.BytesIO()
            folhas_finais[0].save(pdf_output, format="PDF", save_all=True, append_images=folhas_finais[1:], resolution=300.0)
            st.download_button("📥 Baixar PDF Final", pdf_output.getvalue(), "Bazzott_Lovs_Studio.pdf", use_container_width=True)
