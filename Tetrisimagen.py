import streamlit as st
from PIL import Image, ImageChops, ImageFilter, ImageOps, ImageDraw
import io

# --- CONFIGURAÇÕES TÉCNICAS ---
# Definimos a resolução de 300 DPI para garantir precisão na ScanNCut
A4_WIDTH, A4_HEIGHT = 2480, 3508
CM_TO_PX = 118.11 

def tornar_impar(n):
    """Garante que o valor seja ímpar para o correto funcionamento dos filtros PIL."""
    n = int(n)
    return n if n % 2 != 0 else n + 1

# --- MOTOR DE PROCESSAMENTO COM CONTROLE DE LINHA AJUSTÁVEL ---
def gerar_contorno_individual(img, tipo_contorno, sangria_escolhida, linha_ativa, nivel_suavidade, espessura_linha_mm):
    # 1. Limpeza de transparências inúteis ao redor do PNG
    bbox_original = img.getbbox()
    if bbox_original:
        img = img.crop(bbox_original)
    img = img.convert("RGBA")

    # 2. Cálculo de distâncias (mm para pixels)
    if tipo_contorno == "Corte no Desenho (0mm)":
        distancia_px = 2 # Pequeno respiro para a linha não encostar nos pixels da imagem
    else:
        num_mm = float(sangria_escolhida.replace('mm', ''))
        distancia_px = int((num_mm / 10) * CM_TO_PX)
    
    # Espessura da linha preta convertida
    linha_px = int((espessura_linha_mm / 10) * CM_TO_PX)
    
    # 3. Criação da Máscara de Base (Processamento em escala reduzida para velocidade)
    fator = 0.5 
    img_s = img.resize((int(img.width * fator), int(img.height * fator)), Image.LANCZOS)
    p_px_s = int(distancia_px * fator)
    l_px_s = int(linha_px * fator)
    
    # Respiro para garantir que o traço não seja cortado no processamento
    respiro = (p_px_s + l_px_s) * 2 + 120
    
    alpha_base = Image.new("L", (img_s.width + respiro, img_s.height + respiro), 0)
    alpha_base.paste(img_s.split()[3], (respiro // 2, respiro // 2))
    
    # Criar máscara da Sangria (Área Branca)
    mask = alpha_base.filter(ImageFilter.MaxFilter(tornar_impar(p_px_s)))
    
    if nivel_suavidade > 0:
        mask = mask.filter(ImageFilter.GaussianBlur(radius=nivel_suavidade * fator))
        mask = mask.point(lambda p: 255 if p > 128 else 0)

    # Criar máscara da Linha (Área Preta - Stroke Externo)
    # A linha é gerada expandindo a máscara de sangria pela espessura desejada
    mask_linha = mask.filter(ImageFilter.MaxFilter(tornar_impar(l_px_s if l_px_s > 0 else 1)))

    # 4. Redimensionamento para tamanho final (Alta Qualidade)
    mask_f = mask.resize((img.width + distancia_px*2 + 180, img.height + distancia_px*2 + 180), Image.LANCZOS)
    mask_f = mask_f.point(lambda p: 255 if p > 128 else 0)
    
    mask_l_f = mask_linha.resize(mask_f.size, Image.LANCZOS)
    mask_l_f = mask_l_f.point(lambda p: 255 if p > 128 else 0)

    # 5. Montagem do Composto Final
    final_rgba = Image.new("RGBA", mask_f.size, (0, 0, 0, 0))
    
    # Camada Inferior: Sangria Branca
    if tipo_contorno == "Com Sangria":
        final_rgba.paste((255, 255, 255, 255), (0, 0), mask_f)
    
    # Camada Intermédia: Linha Preta de Corte
    if linha_ativa:
        camada_preta = Image.new("RGBA", mask_f.size, (0, 0, 0, 255))
        final_rgba.paste(camada_preta, (0, 0), mask_l_f)
        
        # Fazemos um recorte no "miolo" da linha para ela ser apenas um contorno externo
        interior_limpo = mask_f.filter(ImageFilter.MinFilter(3))
        final_rgba.paste((0,0,0,0), (0,0), interior_limpo)
    
    # Camada Superior: A Imagem Original
    pos_x = (mask_f.width - img.width) // 2
    pos_y = (mask_f.height - img.height) // 2
    img_top = Image.new("RGBA", mask_f.size, (0, 0, 0, 0))
    img_top.paste(img, (pos_x, pos_y))
    final_rgba = Image.alpha_composite(final_rgba, img_top)

    final_bbox = final_rgba.getbbox()
    return final_rgba.crop(final_bbox), mask_f.crop(final_bbox)

# --- LÓGICA DE PAGINAÇÃO E LAYOUT ---
def montar_projeto(lista_config, margem_cm, nivel_suavidade, espessura_linha):
    m_px = int(margem_cm * CM_TO_PX)
    e_px = int(0.15 * CM_TO_PX)
    all_pieces = []
    
    for item in lista_config:
        img_base = item['img'].convert("RGBA")
        alvo_px = item['medida_cm'] * CM_TO_PX
        w, h = img_base.size
        # Redimensionamento proporcional pela altura (ou largura se for maior)
        img_res = img_base.resize((int(w*(alvo_px/h)), int(alvo_px)) if h>w else (int(alvo_px), int(h*(alvo_px/w))), Image.LANCZOS)
        
        pv, pm = gerar_contorno_individual(img_res, item['tipo'], item['sangria_val'], item['linha'], nivel_suavidade, espessura_linha)
        for _ in range(item['quantidade']): 
            all_pieces.append({'img': pv, 'mask': pm})

    folhas = []
    pecas_restantes = all_pieces.copy()
    while pecas_restantes and len(folhas) < 20:
        temp_canvas = Image.new("RGBA", (A4_WIDTH, A4_HEIGHT), (0,0,0,0))
        cx, cy, lh = m_px, m_px, 0
        ainda_cabem = []
        
        for p in pecas_restantes:
            iw, ih = p['img'].size
            if cx + iw > A4_WIDTH - m_px:
                cx, cy, lh = m_px, cy + lh + e_px, 0
            if cy + ih <= A4_HEIGHT - m_px:
                temp_canvas.paste(p['img'], (cx, cy), p['img'])
                cx, lh = cx + iw + e_px, max(lh, ih)
            else: ainda_cabem.append(p)

        bbox = temp_canvas.getbbox()
        if bbox:
            final_page = Image.new("RGB", (A4_WIDTH, A4_HEIGHT), (255, 255, 255))
            l_r, a_r = bbox[2]-bbox[0], bbox[3]-bbox[1]
            off_x, off_y = (A4_WIDTH-l_r)//2 - bbox[0], (A4_HEIGHT-a_r)//2 - bbox[1]
            final_page.paste(temp_canvas, (off_x, off_y), temp_canvas)
            folhas.append(final_page)
        pecas_restantes = ainda_cabem
    return folhas

# --- INTERFACE STREAMLIT ---
st.set_page_config(page_title="ScanNCut Studio Pro", layout="wide")
st.title("✂️ ScanNCut Pro - Layout Final v.2")

with st.sidebar:
    st.header("1. Ajustes Gerais")
    # SLIDER DE ESPESSURA DA LINHA PRETA
    espessura_linha = st.slider("Espessura da Linha de Corte (mm)", 0.1, 10.0, 0.5, step=0.1)
    suavidade = st.slider("Arredondamento de Cantos", 0, 30, 10)
    margem = st.slider("Margem de Segurança Papel (cm)", 0.5, 2.5, 1.0)
    
    st.divider()
    st.header("2. Sincronização em Massa")
    b_size = st.number_input("Tamanho Base (cm)", 1.0, 25.0, 5.0)
    b_qtd = st.number_input("Quantidade Base", 1, 100, 10)
    if st.button("Aplicar a Todos os Uploads"):
        for i in range(100):
            if f"m{i}" in st.session_state: st.session_state[f"m{i}"] = b_size
            if f"q{i}" in st.session_state: st.session_state[f"q{i}"] = b_qtd

u = st.file_uploader("Carregue os seus ficheiros PNG", type="png", accept_multiple_files=True)

if u:
    confs = []
    for i, f in enumerate(u):
        with st.expander(f"⚙️ Configuração: {f.name}", expanded=True):
            c1, c2, c3 = st.columns([1, 2, 2])
            img = Image.open(f)
            with c1: st.image(img, width=90)
            with c2:
                med = st.number_input(f"Tamanho (cm)", 1.0, 25.0, 5.0, key=f"m{i}")
                qtd = st.number_input(f"Quantidade", 1, 100, 10, key=f"q{i}")
            with c3:
                tipo = st.selectbox("Estilo de Corte", ["Com Sangria", "Corte no Desenho (0mm)"], key=f"t{i}")
                # OPÇÃO DE 2MM INCLUÍDA
                sang = st.selectbox("Distância Sangria", ["2mm", "3mm", "5mm", "7mm", "9mm"], index=0, key=f"s{i}")
                lin = st.checkbox("Mostrar Linha de Corte Preta", True, key=f"l{i}")
            confs.append({'img': img, 'medida_cm': med, 'quantidade': qtd, 'tipo': tipo, 'sangria_val': sang, 'linha': lin})

    if st.button("🚀 GERAR PROJETO PARA IMPRESSÃO"):
        with st.spinner("A processar os contornos e a organizar o layout..."):
            folhas = montar_projeto(confs, margem, suavidade, espessura_linha)
            if folhas:
                for idx, f in enumerate(folhas): 
                    st.image(f, caption=f"Página de Impressão {idx+1}", use_container_width=True)
                
                # Conversão para PDF
                pdf_output = io.BytesIO()
                folhas[0].save(pdf_output, format="PDF", save_all=True, append_images=folhas[1:], resolution=300.0)
                st.download_button("📥 Baixar PDF Final (300 DPI)", pdf_output.getvalue(), "projeto_scanncut_pro.pdf", use_container_width=True)
