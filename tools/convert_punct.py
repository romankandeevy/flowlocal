"""Перевести модель расстановки знаков в ONNX + int8.

Зачем отдельным скриптом, а не на лету. Конвертация требует torch и
transformers - это два с лишним гигабайта, которые в приложение не поедут
никогда. Скрипт запускается один раз здесь, результат выкладывается в GitHub
Releases, а приложению остаётся onnxruntime, который у него и так есть.

    python tools/convert_punct.py RUPunct/RUPunct_small out/
    python tools/convert_punct.py kontur-ai/sbert_punc_case_ru out/

Что получается на выходе:

    model.onnx        полная точность, для сверки
    model.int8.onnx   то, что раздаём
    vocab.txt         словарь для нашего токенизатора
    labels.json       что означает каждый выход модели

Токенизатор из transformers в рантайм тоже не едет: он тянет за собой
полбиблиотеки. Вместо него - punct_model.WordPiece на чистом Python, и
labels.json нужен именно ему.

ВАЖНО: этот скрипт запускается в отдельном окружении (см. комментарий выше),
а не в том, где живёт приложение. Ставить torch рядом с приложением незачем.
"""

import json
import os
import sys


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    repo, out = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)

    import torch
    from transformers import AutoConfig, AutoModelForTokenClassification, AutoTokenizer

    print(f"качаю {repo}")
    tok = AutoTokenizer.from_pretrained(repo)
    model = AutoModelForTokenClassification.from_pretrained(repo).eval()
    cfg = AutoConfig.from_pretrained(repo)

    # Словарь и метки - рядом с моделью: рантайму нужны оба, а лезть за ними
    # в интернет он не может (вся программа работает офлайн).
    vocab = tok.get_vocab()
    with open(os.path.join(out, "vocab.txt"), "w", encoding="utf-8") as f:
        for token, _idx in sorted(vocab.items(), key=lambda kv: kv[1]):
            f.write(token + "\n")
    meta = {
        "repo": repo,
        "labels": [cfg.id2label[i] for i in range(len(cfg.id2label))],
        "do_lower_case": bool(getattr(tok, "do_lower_case", True)),
        "max_len": int(getattr(cfg, "max_position_embeddings", 512)),
        "unk": tok.unk_token, "cls": tok.cls_token, "sep": tok.sep_token,
        "pad_id": int(tok.pad_token_id or 0),
    }
    with open(os.path.join(out, "labels.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(f"  словарь: {len(vocab)} токенов, меток: {len(meta['labels'])}")

    # Оси батча и длины делаем динамическими: фразы у людей разной длины, а
    # фиксированная длина заставила бы добивать до максимума и считать пустоту.
    sample = tok("проверка связи", return_tensors="pt")
    names = [n for n in ("input_ids", "attention_mask", "token_type_ids")
             if n in sample]
    args = tuple(sample[n] for n in names)
    path = os.path.join(out, "model.onnx")
    print("экспортирую в ONNX")
    torch.onnx.export(
        model, args, path,
        input_names=names, output_names=["logits"],
        dynamic_axes={n: {0: "batch", 1: "seq"} for n in names}
        | {"logits": {0: "batch", 1: "seq"}},
        opset_version=17, do_constant_folding=True,
    )
    print(f"  {os.path.getsize(path)/1e6:.0f} МБ")

    print("квантизую в int8")
    from onnxruntime.quantization import QuantType, quantize_dynamic

    q = os.path.join(out, "model.int8.onnx")
    # Только веса и только Linear: активации на token-classification квантовать
    # незачем, а качество от этого страдает заметно.
    quantize_dynamic(path, q, weight_type=QuantType.QInt8)
    print(f"  {os.path.getsize(q)/1e6:.0f} МБ")
    print("\nготово:", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
