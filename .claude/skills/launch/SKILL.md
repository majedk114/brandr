---
name: launch
description: إطلاق حساب جديد في محفظة Genx: تجهيز البروفايل (الاسم، الـ bio، الصورة، الـ highlights)، أول 6-9 منشورات، وخطة أول أسبوعين حسب launch.md. استخدمه عند "إطلاق"، "launch"، "نفتح الحساب"، "جهّز البروفايل".
argument-hint: <slug>
---

# الإطلاق

1. `python -m genx context <slug>`. لازم يكون في بحث (`research/research.md`)، وإلا ابدأ بـ `/research`.
2. امشِ على `accounts/<slug>/launch.md` بندًا بندًا، وعلّم المنجز `[x]`.
3. جهّز للاعتماد:
   - 3 خيارات للـ bio (سطرين، بصوت الحساب)، وفكرة صورة البروفايل (prompt Magnific).
   - أسماء الـ highlights حسب السلاسل.
   - **خطة الإطلاق** كخطة أسبوع عادية لكن أكبر: `plans/<week>.md` فيها 6-9 منشورات تبني شكل الصفحة (تنوع السلاسل، والفيديو أولًا)، وتمشي بـ `/plan-week` و`/write-content` العاديين.
4. الشخصيات: ما في إطلاق قبل اعتماد `character.md` وصور مرجعية في `reference_images`.
5. بعد ما يفتح صاحب الحساب الحسابات: حوّل `phase` في config.json إلى `launch`، وسجّل أول لقطة: `python -m genx snapshot <slug> instagram followers=0`.
6. بعد أسبوعين وأول تقرير: `phase` → `growth`.
