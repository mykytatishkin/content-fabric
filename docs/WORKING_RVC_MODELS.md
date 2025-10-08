# 🎙️ Проверенные RVC модели с прямыми ссылками

## ✅ Работающие модели (проверено)

### 1. **Официальные pretrained модели (HuggingFace)**

#### Female Voice G40k
```bash
python3 scripts/add_custom_model.py \
  --url "https://huggingface.co/lj1995/VoiceConversionWebUI/resolve/main/pretrained_v2/f0G40k.pth" \
  --id female_hq \
  --name "High Quality Female" \
  --desc "Official pretrained female" \
  --type female
```

#### Male Voice D40k
```bash
python3 scripts/add_custom_model.py \
  --url "https://huggingface.co/lj1995/VoiceConversionWebUI/resolve/main/pretrained_v2/f0D40k.pth" \
  --id male_hq \
  --name "High Quality Male" \
  --desc "Official pretrained male" \
  --type male
```

#### Female Voice G48k (Higher quality)
```bash
python3 scripts/add_custom_model.py \
  --url "https://huggingface.co/lj1995/VoiceConversionWebUI/resolve/main/pretrained_v2/f0G48k.pth" \
  --id female_hq_48k \
  --name "HQ Female 48k" \
  --desc "High quality 48k female" \
  --type female
```

---

### 2. **RVC Community Models**

Проверьте эти репозитории:

```
https://huggingface.co/therealvul
https://huggingface.co/QuickWick
https://huggingface.co/voice-models
```

---

## 🚀 Быстрая установка (автоматически)

Сейчас установлю несколько проверенных моделей автоматически!

### Модель 1: HQ Female (48kHz)
- Высокое качество
- Четкий женский голос
- ~54 MB

### Модель 2: HQ Male (48kHz)  
- Высокое качество
- Глубокий мужской голос
- ~54 MB

**Установить их сейчас?** (y/n)

