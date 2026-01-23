import streamlit as st
from PIL import Image, ImageOps, ImageFilter
import io
import time

# --- CONFIGURAÇÕES TÉCNICAS ---
A4_WIDTH, A4_HEIGHT = 2480, 3508
CM_TO_PX = 118.11 

def tornar_impar(n):
    n = int(n)
    return n if n % 2 != 0 else n + 1

def gerar_contorno_individual(img, medida_cm, sangria_cm, linha_ativa, nivel_suavidade, espelhar):
    # Criamos uma cópia para não corromper o arquivo original na galeria
    img_copy = img.copy().convert("RGBA")
    
    if espelhar:
        img_copy = ImageOps.mirror(img_copy)

    bbox = img_copy.getbbox()
    if bbox:
        img_copy = img_copy.crop(bbox)

    alvo_px = int(medida_cm * CM_TO_PX)
    w, h = img_copy.size
    proporcao = min(alvo_px / w, alvo_px / h)
    img_copy = img_copy.resize((int(w * proporcao), int(h * proporcao)), Image.LANCZOS)

    dist_px = int(sangria_cm * CM_TO_PX)
    
    if dist_px > 0:
        padding = dist_px + 10
        canvas_alpha = Image.new("L", (img_copy.width + padding*2, img_copy.height + padding*2), 0)
        canvas_alpha.paste(img_copy.split()[3], (padding, padding))
        mask = canvas_alpha.filter(ImageFilter.MaxFilter(tornar_impar(dist_px)))
        if nivel_suavidade > 0:
            mask = mask.filter(ImageFilter.GaussianBlur(radius=nivel_suavidade/2))
            mask = mask.point(lambda p: 255 if p > 128 else 0)
    else:
        mask = img_copy.split()[3].point(lambda p: 255 if p > 128 else 0)

    peca_final = Image.new("RGBA", mask.size if dist_px > 0 else img_copy.size, (0, 0, 0, 0))
    
    if linha_ativa:
        linha_mask = mask.filter(ImageFilter.MaxFilter(3)) if dist_px > 0 else mask
        peca_final.paste((0, 0, 0, 255), (0, 0), linha_mask)
    
    peca_final.paste((255, 255, 255, 255), (0, 0), mask)
    
    if dist_px > 0:
        off_x = (peca_final.width - img_copy.width) // 2
        off_y = (peca_final.height - img_copy.height) // 2
        peca_final.paste(img_copy, (off_x, off_y), img_copy)
    else:
        peca_final.paste(img_copy, (0, 0), img_copy)
    
    return peca_final.crop(peca_final.getbbox())

def montar_folhas(pecas, margem_cm):
    m_px = int(margem_cm * CM_TO_PX)
    folhas = []
    lista_pendente = pecas.copy()
    
    while lista_pendente:
        folha = Image.new("RGBA", (A4_WIDTH, A4_HEIGHT), (0,0,0,0))
        x, y, h_linha = m_px, m_px, 0
        inseridos = []
        for i, p in enumerate(lista_pendente):
            pw, ph = p.size
            if x + pw > A4_WIDTH - m_px:
                x, y, h_linha = m_px, y + h_linha + 10, 0
            if y + ph <= A4_HEIGHT - m_px:
                folha.paste(p, (x, y), p)
                x, h_linha = x + pw + 10, max(h_linha, ph)
                inseridos.append(i)
            else: break
        if not inseridos: break
        for idx in sorted(inseridos, reverse=True): lista_pendente.pop(idx)
        
        f_branca = Image.new("RGB", (A4_WIDTH, A4_HEIGHT), (255, 255, 255))
        f_branca.paste(folha, (0, 0), folha)
        folhas.append(f_branca)
    return folhas

# --- INTERFACE ---
st.set_page_config(page_title="Bazzott Studio FIX", layout="wide")

# Inicialização limpa da galeria
if 'galeria' not in st.session_state:
    st.session_state.galeria = []

with st.sidebar:
    st.title("🛠️ Painel de Controle")
    if st.button("🗑️ LIMPAR TUDO", width="stretch"):
        st.session_state.galeria = []
        st.rerun()
    
    st.divider()
    margem = st.slider("Margem (cm)", 0.3, 1.5, 0.5)
    suave = st.slider("Suavização", 0, 30, 15)

# 1. Uploader sem processamento pesado no loop
u = st.file_uploader("Suba seus arquivos aqui", type="png", accept_multiple_files=True)
if u:
    for f in u:
        # Só adiciona se o ID (nome + tamanho) ainda não estiver lá, ou gera ID único
        # Para permitir a mesma imagem, usamos o tempo atual
        img_id = f"{f.name}_{time.time()}"
        st.session_state.galeria.append({
            "id": img_id,
            "name": f.name,
            "img": Image.open(f).convert("RGBA")
        })
    # Limpa o uploader após carregar para a galeria
    st.rerun()

# 2. Exibição e Configuração
if st.session_state.galeria:
    pecas_preparadas = []
    remover_idx = -1

    for i, item in enumerate(st.session_state.galeria):
        iid = item['id']
        with st.expander(f"🖼️ {item['name']}", expanded=True):
            c1, c2, c3, c4 = st.columns([0.5, 2, 2, 0.5])
            
            with c1:
                st.image(item['img'], width=100)
            
            with c2:
                # Usamos nomes de chaves únicos baseados no iid
                t = st.number_input("Tamanho (cm)", 1.0, 25.0, 4.0, key=f"t_{iid}")
                q = st.number_input("Qtd (unidades)", 1, 500, 1, key=f"q_{iid}")
                
            with c3:
                s = st.slider("Sangria (cm)", 0.0, 1.0, 0.25, step=0.05, key=f"s_{iid}")
                esp = st.checkbox("Espelhar Imagem", key=f"e_{iid}")
                l = st.checkbox("Linha de Corte", True, key=f"l_{iid}")

            with c4:
                if st.button("🗑️", key=f"btn_{iid}"):
                    remover_idx = i

            # Gera a peça conforme as configurações acima
            img_gerada = gerar_contorno_individual(item['img'], t, s, l, suave, esp)
            for _ in range(int(q)):
                pecas_preparadas.append(img_gerada)

    # Lógica de remoção fora do loop para não bugar
    if remover_idx != -1:
        st.session_state.galeria.pop(remover_idx)
        st.rerun()

    # 3. Geração do PDF
    if st.button(f"🚀 GERAR PDF COM {len(pecas_preparadas)} ITENS", width="stretch"):
        with st.spinner("Organizando figuras..."):
            folhas = montar_folhas(pecas_preparadas, margem)
            if folhas:
                for idx, folha in enumerate(folhas):
                    st.image(folha, caption=f"Página {idx+1}", width="stretch")
                
                buf = io.BytesIO()
                folhas[0].save(buf, format="PDF", save_all=True, append_images=folhas[1:], resolution=300.0)
                st.download_button("📥 BAIXAR PDF AGORA", buf.getvalue(), "Bazzott_Final.pdf", width="stretch")
