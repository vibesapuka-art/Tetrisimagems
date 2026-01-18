import streamlit as st
from PIL import Image, ImageChops, ImageFilter, ImageDraw, ImageOps
import io
import random

# Configuração A4 300 DPI
A4_WIDTH = 2480
A4_HEIGHT = 3508
CM_TO_PX = 118.11  # Fator para 300 DPI (1 cm = 118.11 pixels)

def tornar_impar(n):
    n = int(n)
    if n < 1: return 1
    return n if n % 2 != 0 else n + 1

def gerar_contorno_custom(img, sangria_cm, suavidade, linha_ativa, espessura_linha):
    # Respiro proporcional ao tamanho em cm
    respiro = int(sangria_cm * CM_TO_PX * 2) + 80 
    img_expandida = Image.new("RGBA", (img.width + respiro, img.height + respiro), (0, 0, 0, 0))
    img_expandida.paste(img, (respiro // 2, respiro // 2))
    
    alpha = img_expandida.split()[3].point(lambda p: 255 if p > 100 else 0)
    
    # Configuração de Intensidade do Blur/União
    if suavidade == "Baixa": raio_blur, expansao_uniao = 2, 5
    elif suavidade == "Média": raio_blur, expansao_uniao = 8, 25
    else: raio_blur, expansao_uniao = 20, 65 

    mask_unida = alpha.filter(ImageFilter.MaxFilter(size=tornar_impar(expansao_uniao)))
    canvas_fill = Image.new("L", (mask_unida.width + 2, mask_unida.height + 2), 0)
    canvas_fill.paste(mask_unida, (1, 1))
    ImageDraw.floodfill(canvas_fill, (0, 0), 255)
    mask_solida = ImageOps.invert(canvas_fill.crop((1, 1, mask_unida.width + 1, mask_unida.height + 1)))
    mask_bolha = ImageChops.lighter(mask_unida, mask_solida)
    
    sangria_px = int(sangria_cm * CM_TO_PX)
    mask_final = mask_bolha.filter(ImageFilter.MaxFilter(size=tornar_impar(sangria_px))) if sangria_px > 0 else mask_bolha
    mask_final = mask_final.filter(ImageFilter.GaussianBlur(radius=raio_blur))
    mask_final = mask_final.point(lambda p: 255 if p > 120 else 0)

    nova_img = Image.new("RGBA", img_expandida.size, (0, 0, 0, 0))
    if linha_ativa:
        mask_linha = mask_final.filter(ImageFilter.MaxFilter(size=tornar_impar(espessura_linha * 2)))
        nova_img.paste((0,0,0,255), (0, 0), mask_linha)
    
    nova_img.paste((255,255,255,255), (0, 0), mask_final)
    nova_img.paste(img_expandida, (0, 0), img_expandida)
    
    bbox = nova_img.getbbox()
    return (nova_img.crop(bbox), mask_final.crop(bbox)) if bbox else (nova_img, mask_final)

def montar_folha_pro(lista_config, margem_cm, sangria_cm, espaco_cm, suavidade, linha_ativa, modo_layout, permitir_90):
    canvas = Image.new('RGBA', (A4_WIDTH, A4_HEIGHT), (255, 255, 255, 255))
    mask_canvas = Image.new('L', (A4_WIDTH, A4_HEIGHT), 0)
    margem_px = int(margem_cm * CM_TO_PX)
    espaco_px = int(espaco_cm * CM_TO_PX)
    
    all_pieces = []
    total_solicitado = 0
    for item in lista_config:
        img_raw = item['img'].convert("RGBA")
        if item['espelhar']: img_raw = ImageOps.mirror(img_raw)
        
        w_px = int(item['width_cm'] * CM_TO_PX)
        ratio = w_px / img_raw.size[0]
        img_res = img_raw.resize((w_px, int(img_raw.size[1] * ratio)), Image.LANCZOS)
        
        peca, mask_c = gerar_contorno_custom(img_res, sangria_cm, suavidade, linha_ativa, 2)
        peca_90 = peca.rotate(90, expand=True) if permitir_90 else None
        mask_90 = mask_c.rotate(90, expand=True) if permitir_90 else None

        for _ in range(item['quantidade']):
            total_solicitado += 1
            all_pieces.append({'orig': (peca, mask_c), 'rot': (peca_90, mask_90) if permitir_90 else None})

    all_pieces.sort(key=lambda x: x['orig'][0].size[1], reverse=True)
    contador_sucesso = 0

    if modo_layout == "Aleatório (Tetris)":
        for p in all_pieces:
            encaixou = False
            opcoes = [p['orig']]
            if p['rot']: opcoes.append(p['rot'])
            for img_p, mask_p in opcoes:
                iw, ih = img_p.size
                for _ in range(1500):
                    tx = random.randint(margem_px, A4_WIDTH - iw - margem_px)
                    ty = random.randint(margem_px, A4_HEIGHT - ih - margem_px)
                    if not ImageChops.multiply(mask_canvas.crop((tx, ty, tx + iw, ty + ih)), mask_p).getbbox():
                        canvas.paste(img_p, (tx, ty), img_p)
                        mask_canvas.paste(mask_p, (tx, ty), mask_p)
                        encaixou = True
                        contador_sucesso += 1
                        break
                if encaixou: break
    else:
        curr_x, curr_y = margem_px, margem_px
        linha_h = 0
        for p in all_pieces:
            img, m = p['orig']
            iw, ih = img.size
            if curr_x + iw + margem_px > A4_WIDTH:
                curr_x = margem_px
                curr_y += linha_h + espaco_px
                linha_h = 0
            if curr_y + ih + margem_px <= A4_HEIGHT - margem_px:
                canvas.paste(img, (curr_x, curr_y), img)
                curr_x += iw + espaco_px
                linha_h = max(linha_h, ih)
                contador_sucesso += 1

    return canvas, total_solicitado, contador_sucesso

# Interface Streamlit
st.set_page_config(page_title="ScanNCut Pro Studio (cm)", layout="wide")

with st.sidebar:
    st.header("⚙️ Configurações (cm)")
    modo_layout = st.radio("Encaixe", ["Aleatório (Tetris)", "Linhas"])
    permitir_90 = st.checkbox("Girar 90° automático", value=True)
    margem_folha = st.slider("Margem da folha (cm)", 0.5, 3.0, 1.0, 0.1)
    espaco_entre = st.slider("Espaço entre peças (cm)", 0.0, 2.0, 0.2, 0.05)
    
    st.header("🎨 Estilo do Corte")
    sangria = st.slider("Sangria Branca (cm)", 0.0, 2.0, 0.4, 0.1)
    suavidade_sel = st.select_slider("Suavidade", options=["Baixa", "Média", "Alta"], value="Alta")
    linha_on = st.toggle("Linha de Corte Preta", value=True)

st.title("✂️ ScanNCut Pro: Calibrado em Centímetros")

uploads = st.file_uploader("Suba seus arquivos PNG", type=['png'], accept_multiple_files=True)

if uploads:
    config_list = []
    cols = st.columns(4)
    for i, arq in enumerate(uploads):
        with cols[i % 4]:
            img_aberta = Image.open(arq)
            st.image(img_aberta, width=100) 
            larg_cm = st.number_input(f"Largura (cm)", 1.0, 20.0, 7.0, 0.1, key=f"w_{i}")
            qtd = st.number_input(f"Quantidade", 1, 100, 1, key=f"q_{i}")
            espelhar = st.checkbox(f"Espelhar", key=f"m_{i}")
            config_list.append({'img': img_aberta, 'width_cm': larg_cm, 'quantidade': qtd, 'espelhar': espelhar})

    if st.button("🚀 GERAR FOLHA OTIMIZADA"):
        folha_final, total, sucesso = montar_folha_pro(config_list, margem_folha, sangria, espaco_entre, suavidade_sel, linha_on, modo_layout, permitir_90)
        
        st.subheader("📊 Resumo da Produção")
        c1, c2, c3 = st.columns(3)
        c1.metric("Peças Solicitadas", f"{total}")
        c2.metric("Peças Encaixadas", f"{sucesso}")
        aprov = (sucesso/total)*100 if total > 0 else 0
        c3.metric("Aproveitamento", f"{aprov:.1f}%")

        if sucesso < total:
            st.warning(f"⚠️ Faltaram {total - sucesso} peças por falta de espaço.")
        
        st.image(folha_final, use_container_width=True)
        
        col_pdf, col_png = st.columns(2)
        # Download PDF
        buf_pdf = io.BytesIO()
        folha_final.convert("RGB").save(buf_pdf, format="PDF", resolution=300.0)
        col_pdf.download_button("📥 Baixar PDF (Imprimir)", buf_pdf.getvalue(), "folha_scanncut.pdf", use_container_width=True)
        # Download PNG
        buf_png = io.BytesIO()
        folha_final.save(buf_png, format="PNG")
        col_png.download_button("🖼️ Baixar PNG (Edição)", buf_png.getvalue(), "folha_scanncut.png", use_container_width=True)
