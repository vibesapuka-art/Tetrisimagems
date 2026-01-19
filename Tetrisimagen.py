import streamlit as st
from PIL import Image, ImageChops, ImageFilter, ImageDraw, ImageOps
import io
import random

A4_WIDTH = 2480
A4_HEIGHT = 3508
CM_TO_PX = 118.11 

def tornar_impar(n):
    n = int(n)
    if n < 1: return 1
    return n if n % 2 != 0 else n + 1

def gerar_contorno_fast(img, sangria_cm, linha_ativa):
    # Respiro maior para garantir que a máscara de colisão pegue todo o contorno
    respiro = int(sangria_cm * CM_TO_PX * 2) + 60 if sangria_cm > 0 else 30
    img_exp = Image.new("RGBA", (img.width + respiro, img.height + respiro), (0, 0, 0, 0))
    img_exp.paste(img, (respiro // 2, respiro // 2))
    
    alpha = img_exp.split()[3].point(lambda p: 255 if p > 100 else 0)
    
    # Gerar a máscara de contorno (bolha)
    n_max = tornar_impar(20) 
    mask_base = alpha.filter(ImageFilter.MaxFilter(n_max))
    
    if sangria_cm > 0:
        sangria_px = tornar_impar(int(sangria_cm * CM_TO_PX))
        # A máscara final (mask_corte) agora é o que define o limite físico da peça
        mask_corte = mask_base.filter(ImageFilter.MaxFilter(sangria_px))
        mask_corte = mask_corte.filter(ImageFilter.GaussianBlur(4)).point(lambda p: 255 if p > 128 else 0)
    else:
        mask_corte = alpha.filter(ImageFilter.GaussianBlur(1)).point(lambda p: 255 if p > 128 else 0)

    nova_img = Image.new("RGBA", img_exp.size, (0, 0, 0, 0))
    
    # Desenha o contorno branco e a linha preta
    if sangria_cm > 0:
        if linha_ativa:
            # Linha preta ligeiramente maior para ficar por fora
            borda_preta = mask_corte.filter(ImageFilter.MaxFilter(3))
            nova_img.paste((0,0,0,255), (0,0), borda_preta)
        
        nova_img.paste((255,255,255,255), (0,0), mask_corte)
        
    nova_img.paste(img_exp, (0,0), img_exp)
    bbox = nova_img.getbbox()
    
    # Retorna a imagem final e a MÁSCARA DO CONTORNO para o Tetris usar como limite
    if bbox:
        return nova_img.crop(bbox), mask_corte.crop(bbox)
    return nova_img, mask_corte

# ... (Funções de folha e PDF permanecem as mesmas)

def montar_multiplas_folhas_inteligente(lista_config, margem_cm, sangria_cm, linha_ativa, permitir_90):
    m_px = int(margem_cm * CM_TO_PX)
    # Espaçamento mínimo de segurança (Buffer) entre as linhas pretas
    e_px = int(0.10 * CM_TO_PX) 
    all_pieces = []
    
    e_imagem_unica = len(lista_config) == 1

    for item in lista_config:
        img = item['img'].convert("RGBA")
        if item['espelhar']: img = ImageOps.mirror(img)
        
        # Lógica de sincronização pelo maior lado
        w_orig, h_orig = img.size
        medida_alvo_px = item['medida_cm'] * CM_TO_PX
        if h_orig > w_orig:
            nova_h = int(medida_alvo_px)
            nova_w = int(w_orig * (medida_alvo_px / h_orig))
        else:
            nova_w = int(medida_alvo_px)
            nova_h = int(h_orig * (medida_alvo_px / w_orig))
            
        img = img.resize((nova_w, nova_h), Image.Resampling.LANCZOS)

        # Aqui está o segredo: peca (visual) e m_c (máscara de limite/colisão)
        peca, m_c = gerar_contorno_fast(img, sangria_cm, linha_ativa)
        
        # Adiciona um pequeno "respiro" na máscara de colisão para as linhas não se tocarem
        m_c_colisao = m_c.filter(ImageFilter.MaxFilter(tornar_impar(e_px)))
        
        p_90, m_90 = (peca.rotate(90, expand=True), m_c_colisao.rotate(90, expand=True)) if permitir_90 else (None, None)

        for _ in range(item['quantidade']):
            all_pieces.append({'orig': (peca, m_c_colisao), 'rot': (p_90, m_90)})

    # Organização Tetris com colisão baseada na Sangria
    all_pieces.sort(key=lambda x: x['orig'][0].size[0] * x['orig'][0].size[1], reverse=True)
    
    # ... (Continua com a lógica de montagem de múltiplas folhas)
