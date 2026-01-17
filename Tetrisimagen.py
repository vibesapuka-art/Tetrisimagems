import streamlit as st
from PIL import Image, ImageChops, ImageFilter
import io
import random

# Configuração da Folha A4 em 300 DPI
A4_WIDTH = 2480
A4_HEIGHT = 3508
MM_TO_PX = 11.81

def gerar_contorno_suave(img, sangria_mm, espessura_linha):
    """Cria sangria branca lisa, sem buracos internos e com linha preta de guia"""
    sangria_px = int(sangria_mm * MM_TO_PX)
    # Extrai o canal alpha (transparência)
    alpha = img.split()[3]
    
    # --- PASSO 1: FECHAR BURACOS INTERNOS ---
    # Criamos uma máscara sólida e usamos filtros para 'soldar' vãos internos
    mask_cheia = alpha.point(lambda p: 255 if p > 10 else 0)
    # Filtro de expansão e erosão pesada para fechar buracos como o do rabo
    mask_cheia = mask_cheia.filter(ImageFilter.MaxFilter(31))
    mask_cheia = mask_cheia.filter(ImageFilter.MinFilter(31))

    # --- PASSO 2: CRIAR SANGRIA E SUAVIZAR ---
    # Expandimos para o tamanho da sangria desejada
    mask_sangria = mask_cheia.filter(ImageFilter.MaxFilter(sangria_px * 2 + 1))
    
    # Suavização Gaussiana para eliminar o efeito 'escada' (colinas)
    mask_sangria = mask_sangria.filter(ImageFilter.GaussianBlur(radius=4))
    # Binarização para deixar a borda nítida novamente, mas com curvas suaves
    mask_sangria = mask_sangria.point(lambda p: 255 if p > 128 else 0)

    # --- PASSO 3: LINHA PRETA EXTERNA ---
    # Criamos a linha preta um pouco maior que a sangria branca
    mask_linha = mask_sangria.filter(ImageFilter.MaxFilter(espessura_linha * 2 + 1)) 
    
    # Montagem da imagem final da peça
    peca_final = Image.new("RGBA", img.size, (0, 0, 0, 0))
    
    # Camada 1: Linha Preta (Fundo)
    preto = Image.new("RGBA", img.size, (0, 0, 0, 255))
    peca_final.paste(preto, (0, 0), mask_linha)
    
    # Camada 2: Sangria Branca (Meio)
    branco = Image.new("RGBA", img.size, (255, 255, 255, 255))
    peca_final.paste(branco, (0, 0), mask_sangria)
    
    # Camada 3: Desenho Original (Topo)
    peca_final.paste(img, (0, 0), img)
    
    return peca_final, mask_linha

def montar_folha_final(lista_config, margem_mm, sangria_mm, espaco_mm, espessura_linha):
    canvas = Image.new('RGBA', (A4_WIDTH, A4_HEIGHT), (255, 255, 255, 255))
    mask_canvas = Image.new('L', (A4_WIDTH, A4_HEIGHT), 0)
    
    margem_px = int(margem_mm * MM_TO_PX)
    espaco_px = int(espaco_mm * MM_TO_PX)
    
    processed = []
    for item in lista_config:
        img_orig = item['img'].convert("RGBA")
        w_px = int(item['width_mm'] * MM_TO_PX)
        ratio = w_px / img_orig.size[0]
        img_res = img_orig.resize((w_px, int(img_orig.size[1] * ratio)), Image.LANCZOS)
        
        # Crop automático para evitar áreas vazias grandes
        bbox = img_res.getbbox()
        if bbox: img_res = img_res.crop(bbox)
            
        # Gera a peça com contorno profissional
        img_com_contorno, mask_colisao = gerar_contorno_suave(img_res, sangria_mm, espessura_linha)
        
        # Adiciona o espaçamento de segurança na máscara de colisão
        if espaco_px > 0:
            m_colisao = mask_colisao.filter(ImageFilter.MaxFilter(espaco_px * 2 + 1))
        else:
            m_colisao = mask_colisao
            
        processed.append({'img': img_com_contorno, 'mask': m_colisao})

    # Ordenar pelas maiores para garantir encaixe
    processed.sort(key=lambda x: x['img'].size[1], reverse=True)

    for p in processed:
        img, m = p['img'], p['mask']
        iw, ih = img.size
        sucesso = False
        
        # 5000 tentativas aleatórias para buscar vãos e encaixes 'Tetris'
        for _ in range(5000): 
            tx = random.randint(margem_px, A4_WIDTH - iw - margem_px)
            ty = random.randint(margem_px, A4_HEIGHT - ih - margem_px)
            
            pedaco_canvas = mask_canvas.crop((tx, ty, tx + iw, ty + ih))
            if not ImageChops.multiply(pedaco_canvas, m).getbbox():
                canvas.paste(img, (tx, ty), img)
                mask_canvas.paste(m, (tx, ty), m)
                sucesso = True
                break
        
        if not sucesso:
            st.error(f"Não coube uma das imagens (Largura: {iw}px).")

    return canvas

# --- INTERFACE STREAMLIT ---
st.set_page_config(page_title="ScanNCut Pro Helper", layout="wide")
st.title("🎯 ScanNCut: Contorno Suave + Sangria")

st.sidebar.header("⚙️ Ajustes de Produção")
sangria = st.sidebar.number_input("Sangria Branca (mm)", 0.5, 10.0, 2.5, 0.5)
espaco_peças = st.sidebar.number_input("Espaço entre Linhas Pretas (mm)", 0.0, 10.0, 1.0, 0.5)
linha_px = st.sidebar.slider("Espessura da Linha do Scanner (px)", 1, 5, 2)
margem_f = st.sidebar.slider("Margem da Folha (mm)", 5, 30, 10)

st.sidebar.markdown("---")
st.sidebar.info("A linha preta será contínua e sem furos internos, ideal para o scanner da ScanNCut.")

arquivos = st.file_uploader("Suba seus personagens PNG", type=['png'], accept_multiple_files=True)

if arquivos:
    config_list = []
    cols = st.columns(4)
    for i, arq in enumerate(arquivos):
        with cols[i % 4]:
            img_aberta = Image.open(arq)
            st.image(img_aberta, use_container_width=True)
            larg_mm = st.number_input(f"Largura (mm):", 10, 250, 70, key=f"w_{i}")
            config_list.append({'img': img_aberta, 'width_mm': larg_mm})

    if st.button("🚀 GERAR MONTAGEM PARA CORTE DIRETO"):
        with st.spinner('Limpando contornos e encaixando peças...'):
            folha_pronta = montar_folha_final(config_list, margem_f, sangria, espaco_peças, linha_px)
            st.image(folha_pronta, use_container_width=True)
            
            # Preparar PDF
            pdf_output = io.BytesIO()
            folha_pronta.convert("RGB").save(pdf_output, format="PDF", resolution=300.0)
            st.download_button("📥 Baixar PDF para Impressão", pdf_output.getvalue(), "folha_scanncut_pro.pdf")
