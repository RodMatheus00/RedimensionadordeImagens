from pathlib import Path
import os
import tempfile
import threading
import queue
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from PIL import Image, ImageOps, UnidentifiedImageError

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}

try:
    RESAMPLE_FILTER = Image.Resampling.LANCZOS
except AttributeError:
    RESAMPLE_FILTER = Image.LANCZOS


class RedimensionadorApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Redimensionador de Imagens")
        self.root.geometry("780x560")
        self.root.minsize(720, 520)

        self.queue = queue.Queue()
        self.processando = False

        self.pasta_var = tk.StringVar()
        self.max_largura_var = tk.StringVar(value="1024")
        self.max_altura_var = tk.StringVar(value="768")
        self.qualidade_var = tk.StringVar(value="90")

        self.total_arquivos = 0
        self.ok = 0
        self.ignoradas = 0
        self.erros = 0

        self._criar_layout()
        self._poll_queue()

    def _criar_layout(self):
        container = ttk.Frame(self.root, padding=14)
        container.pack(fill="both", expand=True)

        ttk.Label(
            container,
            text="Redimensionador de Imagens",
            font=("Segoe UI", 15, "bold")
        ).pack(anchor="w", pady=(0, 12))

        frame_entrada = ttk.LabelFrame(container, text="Pasta", padding=10)
        frame_entrada.pack(fill="x", pady=(0, 10))

        ttk.Label(frame_entrada, text="Selecione a pasta com as imagens:").grid(row=0, column=0, sticky="w")
        ttk.Entry(frame_entrada, textvariable=self.pasta_var).grid(row=1, column=0, sticky="ew", padx=(0, 8), pady=(4, 0))
        ttk.Button(frame_entrada, text="Selecionar...", command=self.escolher_pasta).grid(row=1, column=1, sticky="ew", pady=(4, 0))
        frame_entrada.columnconfigure(0, weight=1)

        frame_config = ttk.LabelFrame(container, text="Configurações", padding=10)
        frame_config.pack(fill="x", pady=(0, 10))

        ttk.Label(frame_config, text="Largura máxima:").grid(row=0, column=0, sticky="w")
        ttk.Entry(frame_config, textvariable=self.max_largura_var, width=12).grid(row=1, column=0, sticky="w", pady=(4, 0))

        ttk.Label(frame_config, text="Altura máxima:").grid(row=0, column=1, sticky="w", padx=(16, 0))
        ttk.Entry(frame_config, textvariable=self.max_altura_var, width=12).grid(row=1, column=1, sticky="w", padx=(16, 0), pady=(4, 0))

        ttk.Label(frame_config, text="Qualidade JPEG (1 a 100):").grid(row=0, column=2, sticky="w", padx=(16, 0))
        ttk.Entry(frame_config, textvariable=self.qualidade_var, width=12).grid(row=1, column=2, sticky="w", padx=(16, 0), pady=(4, 0))

        ttk.Label(
            frame_config,
            text="As imagens serão substituídas diretamente pelos arquivos redimensionados."
        ).grid(row=2, column=0, columnspan=3, sticky="w", pady=(12, 0))

        frame_acoes = ttk.Frame(container)
        frame_acoes.pack(fill="x", pady=(0, 10))

        self.btn_iniciar = ttk.Button(
            frame_acoes,
            text="Iniciar processamento",
            command=self.iniciar_processamento
        )
        self.btn_iniciar.pack(side="left")

        self.progress = ttk.Progressbar(frame_acoes, mode="determinate")
        self.progress.pack(side="left", fill="x", expand=True, padx=12)

        self.lbl_status = ttk.Label(frame_acoes, text="Pronto")
        self.lbl_status.pack(side="left")

        frame_log = ttk.LabelFrame(container, text="Log", padding=10)
        frame_log.pack(fill="both", expand=True)

        self.txt_log = tk.Text(frame_log, height=18, wrap="word", state="disabled")
        self.txt_log.pack(side="left", fill="both", expand=True)

        scroll = ttk.Scrollbar(frame_log, orient="vertical", command=self.txt_log.yview)
        scroll.pack(side="right", fill="y")
        self.txt_log.configure(yscrollcommand=scroll.set)

    def escolher_pasta(self):
        pasta = filedialog.askdirectory(title="Selecione a pasta com as imagens")
        if pasta:
            self.pasta_var.set(pasta)

    def log(self, mensagem: str):
        self.txt_log.configure(state="normal")
        self.txt_log.insert("end", mensagem + "\n")
        self.txt_log.see("end")
        self.txt_log.configure(state="disabled")

    def validar_campos(self):
        pasta = self.pasta_var.get().strip()
        if not pasta:
            messagebox.showwarning("Aviso", "Selecione uma pasta.")
            return None

        pasta_entrada = Path(pasta)
        if not pasta_entrada.exists() or not pasta_entrada.is_dir():
            messagebox.showerror("Erro", "A pasta selecionada é inválida.")
            return None

        try:
            max_largura = int(self.max_largura_var.get())
            max_altura = int(self.max_altura_var.get())
            qualidade = int(self.qualidade_var.get())
        except ValueError:
            messagebox.showerror("Erro", "Largura, altura e qualidade devem ser números inteiros.")
            return None

        if max_largura <= 0 or max_altura <= 0:
            messagebox.showerror("Erro", "Largura e altura devem ser maiores que zero.")
            return None

        if not (1 <= qualidade <= 100):
            messagebox.showerror("Erro", "A qualidade JPEG deve estar entre 1 e 100.")
            return None

        return pasta_entrada, (max_largura, max_altura), qualidade

    def salvar_imagem_substituindo(self, img: Image.Image, destino: Path, qualidade: int) -> None:
        ext = destino.suffix.lower()
        destino.parent.mkdir(parents=True, exist_ok=True)

        fd, temp_path_str = tempfile.mkstemp(
            dir=str(destino.parent),
            prefix=destino.stem + "_tmp_",
            suffix=ext
        )
        os.close(fd)

        temp_path = Path(temp_path_str)

        try:
            if ext in {".jpg", ".jpeg"}:
                if img.mode in ("RGBA", "LA"):
                    fundo = Image.new("RGB", img.size, (255, 255, 255))
                    fundo.paste(img, mask=img.getchannel("A"))
                    img = fundo
                elif img.mode != "RGB":
                    img = img.convert("RGB")

                img.save(
                    temp_path,
                    quality=qualidade,
                    optimize=True,
                    progressive=True
                )

            elif ext == ".png":
                img.save(temp_path, optimize=True)

            else:
                img.save(temp_path)

            # aqui o arquivo original já está fechado
            os.replace(temp_path, destino)

        finally:
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except Exception:
                    pass

    def processar_imagem(self, origem: Path, max_size: tuple[int, int], qualidade: int):
        try:
            # abre e fecha o arquivo original antes de substituir
            with Image.open(origem) as img_original:
                img_corrigida = ImageOps.exif_transpose(img_original).copy()

            tamanho_original = img_corrigida.size
            precisa_reduzir = (
                img_corrigida.width > max_size[0]
                or img_corrigida.height > max_size[1]
            )

            if not precisa_reduzir:
                img_corrigida.close()
                return tamanho_original, tamanho_original, origem, "mantida"

            img_saida = img_corrigida.copy()
            img_corrigida.close()

            img_saida.thumbnail(max_size, RESAMPLE_FILTER)
            novo_tamanho = img_saida.size

            self.salvar_imagem_substituindo(img_saida, origem, qualidade)
            img_saida.close()

            return tamanho_original, novo_tamanho, origem, "substituída"

        except UnidentifiedImageError:
            return None
        except Exception as e:
            return f"erro: {e}"

    def iniciar_processamento(self):
        if self.processando:
            return

        dados = self.validar_campos()
        if not dados:
            return

        pasta_entrada, max_size, qualidade = dados

        arquivos = [
            p for p in pasta_entrada.rglob("*")
            if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
        ]

        if not arquivos:
            messagebox.showinfo("Resultado", "Nenhuma imagem encontrada.")
            return

        confirmar = messagebox.askyesno(
            "Confirmar",
            "As imagens originais serão substituídas.\n\nDeseja continuar?"
        )
        if not confirmar:
            return

        self.total_arquivos = len(arquivos)
        self.ok = 0
        self.ignoradas = 0
        self.erros = 0

        self.progress["value"] = 0
        self.progress["maximum"] = self.total_arquivos
        self.lbl_status.config(text=f"0 / {self.total_arquivos}")
        self.btn_iniciar.config(state="disabled")
        self.processando = True

        self.txt_log.configure(state="normal")
        self.txt_log.delete("1.0", "end")
        self.txt_log.configure(state="disabled")

        self.log(f"Processando {self.total_arquivos} imagem(ns)...")
        self.log("")

        thread = threading.Thread(
            target=self._worker,
            args=(arquivos, max_size, qualidade),
            daemon=True
        )
        thread.start()

    def _worker(self, arquivos, max_size, qualidade):
        for i, arquivo in enumerate(arquivos, start=1):
            resultado = self.processar_imagem(arquivo, max_size, qualidade)

            if resultado is None:
                self.ignoradas += 1
                self.queue.put(("log", f"[IGNORADO] {arquivo} (não reconhecido como imagem)"))

            elif isinstance(resultado, str) and resultado.startswith("erro:"):
                self.erros += 1
                self.queue.put(("log", f"[ERRO] {arquivo} -> {resultado}"))

            else:
                original, novo, destino, acao = resultado
                self.ok += 1
                self.queue.put((
                    "log",
                    f"[OK] {arquivo.name}: {original[0]}x{original[1]} -> {novo[0]}x{novo[1]} ({acao})"
                ))

            self.queue.put(("progress", i))

        resumo = [
            "",
            "Resumo",
            f"OK: {self.ok}",
            f"Ignoradas: {self.ignoradas}",
            f"Erros: {self.erros}",
        ]

        self.queue.put(("log", "\n".join(resumo)))
        self.queue.put(("done", None))

    def _poll_queue(self):
        try:
            while True:
                tipo, valor = self.queue.get_nowait()

                if tipo == "log":
                    self.log(valor)

                elif tipo == "progress":
                    self.progress["value"] = valor
                    self.lbl_status.config(text=f"{valor} / {self.total_arquivos}")

                elif tipo == "done":
                    self.processando = False
                    self.btn_iniciar.config(state="normal")
                    self.lbl_status.config(text="Concluído")
                    messagebox.showinfo("Concluído", "Processamento finalizado.")
        except queue.Empty:
            pass

        self.root.after(100, self._poll_queue)


def main():
    root = tk.Tk()
    app = RedimensionadorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()