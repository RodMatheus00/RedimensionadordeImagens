# Redimensionador de Imagens

Aplicativo desktop (Tkinter) que redimensiona em lote todas as imagens de uma pasta para uma largura máxima, mantendo a proporção.

Formatos: JPG, JPEG, PNG, BMP, TIF, TIFF e WEBP.

## Como rodar

```
pip install pillow
python redimensionar_imagens.py
```

## Gerar o executável

```
pip install pyinstaller
pyinstaller redimensionar_imagens.spec
```

O `.exe` é gerado em `dist/`.
