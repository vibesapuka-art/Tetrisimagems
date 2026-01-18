import streamlit as st
from PIL import Image, ImageChops, ImageFilter, ImageDraw, ImageOps
import io
import random

# Configuração A4 300 DPI
A4_WIDTH = 2480
A4_HEIGHT = 3508
MM_TO_PX = 11.81

def tornar_impar(n):
    n = int(n)
    if n < 1: return 1
    return n if n % 2 != 0 else n + 1

def gerar_contorno_custom(img, sangria_mm, suavidade, linha_ativa, espessura_linha):
    # Respiro para não cortar as bordas
    respiro = int(sangria_mm * MM_TO_PX * 2) + 60 
    img_expandida = Image.new("RGBA", (img.width + respiro, img.height + respiro), (0, 0, 0, 0))
    img_expandida.paste(img, (respiro // 2, respiro // 2))
    
    alpha = img_expandida.split()[3].point(lambda p: 255 if p > 100 else 0)
    
    # Configuração de Intensidade
    if suavidade == "Baixa":
        raio_blur, expansao_uniao = 2, 5
    elif suavidade == "Média":
        raio_blur, expansao_uniao = 8, 25
    else: # Alta (Efeito Bolha)
        raio_blur, expansao_uniao = 20, 65 

    # Unificação e Preenchimento
    mask_unida = alpha.filter(ImageFilter.MaxFilter(size=tornar_impar(expansao_uniao)))
    canvas_fill = Image.new("L", (mask_unida.width + 2, mask_unida.height + 2), 0)
    canvas_fill.paste(mask_unida, (1, 1))
    ImageDraw.floodfill(canvas_fill, (0, 0), 255)
    mask_solida = ImageOps.invert(canvas_fill.crop((1, 1, mask_unida.width + 1, mask_unida.height + 1)))
    mask_bolha = ImageChops.lighter(mask_unida, mask_solida)
    
    # Sangria e Suavização
    sangria_px = int(sangria_mm * MM_TO_PX)
    mask_final = mask_bolha.filter(ImageFilter.MaxFilter(size=tornar_impar(sangria_px))) if sangria_px > 0 else mask_bolha
    mask_final = mask_final.filter(ImageFilter.GaussianBlur(radius=raio_blur))
    mask_final = mask_final.point(lambda p: 255 if p > 120 else 0)

    # Montagem da Peça
    nova_img = Image.new("RGBA", img_expandida.size, (0, 0, 0, 0))
    branco = Image.new("RGBA", img_expandida.size, (255, 255, 255, 255))
    
    if linha_ativa:
        mask_linha = mask_final.filter(ImageFilter.MaxFilter(size=tornar_impar(espessura_linha * 2)))
        preto = Image.new("RGBA", img_expandida.size, (0, 0, 0, 255))
        nova_img.paste(preto, (0, 0), mask_linha)
    
    nova_img.paste(branco, (0, 0), mask_final)
    nova_img.paste(img_expandida, (0, 0), img_expandida)
    
    bbox = nova_img.getbbox()
    return (nova_img.crop(bbox), mask_final.crop(bbox)) if bbox else (nova_img, mask_final)

def montar_folha_pro(lista_config, margem_mm, sangria_mm, espaco_mm, suavidade, linha_ativa, linha_px, modo_layout):
    canvas = Image.new('RGBA', (A4_WIDTH, A4_HEIGHT), (255, 255, 255, 255))
    mask_canvas = Image.new('L', (A4_WIDTH, A4_HEIGHT), 0)
    margem_px = int(margem_mm * MM_TO_PX)
    espaco_px = int(espaco_mm * MM_TO_PX)
    
    all_pieces = []
    for item in lista_config:
        img_raw = item['img'].convert("RGBA")
        w_px = int(item['width_mm'] * MM_TO_PX)
        ratio = w_px / img_raw.size[0]
        img_res = img_raw.resize((w_px, int(img_raw.size[1] * ratio)), Image.LANCZOS)
        
        peca, mask_c = gerar_contorno_custom(img_res, sangria_mm, suavidade, linha_ativa, linha_px)
        
        for _ in range(item['quantidade']):
            all_pieces.append({'img': peca, 'mask': mask_c})

    if modo_layout == "Aleatório (Tetris)":
        all_pieces.sort(key=lambda x: x['img'].size[1], reverse=True)
        for p in all_pieces:
            img, m = p['img'], p['mask']
            iw, ih = img.size
            for _ in range(5000): 
                tx = random.randint(margem_px, A4_WIDTH - iw - margem_px)
                ty = random.randint(margem_px, A4_HEIGHT - ih - margem_px)
                if not ImageChops.multiply(mask_canvas.crop((tx, ty, tx + iw, ty + ih)), m).getbbox():
                    canvas.paste(img, (tx, ty), img)
                    mask_canvas.paste(m, (tx, ty), m)
                    break
    else: # MODO EM LINHA
        curr_x, curr_y = margem_px, margem_px
        linha_h = 0
        for p in all_pieces:
            img, m = p['img'], p['mask']
            iw, ih = img.size
            
            if curr_x + iw + margem_px > A4_WIDTH:
                curr_x = margem_px
                curr_y += linha_h + espaco_px
                linha_h = 0
            
            if curr_y + ih + margem_px > A4_HEIGHT:
                break # Fim da folha
                
            canvas.paste(img, (curr_x, curr_y), img)
            curr_x += iw + espaco_px
            linha_h = max(linha_h, ih)

    return canvas

# Interface
st.set_page_config(page_title="ScanNCut Pro Studio", layout="wide")

with st.sidebar:
    st.header("📏 Configurações de Layout")
    modo_layout = st.radio("Modo de Organização", ["Aleatório (Tetris)", "Organizado (Em Linhas)"])
    margem_folha = st.slider("Margem da folha (mm)", 5, 20, 10)
    espaco_entre = st.slider("Espaço entre peças (mm)", 0.0, 10.0, 1.5)

    st.header("🎨 Estilo do Contorno")
    sangria = st.slider("Sangria Branca (mm)", 0.0, 15.0, 4.0)
    suavidade_sel = st.select_slider("Suavidade", options=["Baixa", "Média", "Alta"], value="Alta")
    
    st.header("🛠️ Linha de Corte")
    linha_on = st.toggle("Ativar Linha Preta", value=True)
    linha_w = st.slider("Espessura (px)", 1, 5, 2)

st.title("✂️ Organizador Profissional de Topos")

uploads = st.file_uploader("Selecione seus PNGs", type=['png'], accept_multiple_files=True)

if uploads:
    config_list = []
    cols = st.columns(4)
    for i, arq in enumerate(uploads):
        with cols[i % 4]:
            img_aberta = Image.open(arq)
            st.image(img_aberta, width=100) 
            larg = st.number_input(f"Largura (mm)", 10, 300, 70, key=f"w_{i}")
            qtd = st.number_input(f"Quantidade", 1, 100, 1, key=f"q_{i}")
            config_list.append({'img': img_aberta, 'width_mm': larg, 'quantidade': qtd})

    if st.button("🚀 GERAR FOLHA"):
        with st.spinner('Montando folha...'):
            folha = montar_folha_pro(config_list, margem_folha, sangria, espaco_entre, suavidade_sel, linha_on, linha_w, modo_layout)
            st.image(folha, use_container_width=True)
            buf = io.BytesIO()
            folha.convert("RGB").save(buf, format="PDF", resolution=300.0)
            st.download_button("📥 Baixar PDF", buf.getvalue(), "folha_final.pdf")
