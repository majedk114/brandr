---
name: write-content
description: كتابة منشورات خطة أسبوع معتمدة لحساب واحد في محفظة Genx، مع prompt إنتاج لكل منشور، وتمريرها على القواعد ثم للمراجعة. استخدمه عند "اكتب المحتوى"، "write content"، "جهّز منشورات <حساب>".
argument-hint: <slug> [YYYY-Www]
---

# كتابة المحتوى

1. `python -m genx context <slug>` واقرأ الخطة المعتمدة. لو الخطة ما معتمدة (`plan-status`)، وقّف واقترح `/plan-week`.
2. لكل سطر في الخطة اكتب منشور. فكّر كمحرر صارم قبل ما تحفظ:
   - **الخطاف** (أول سطر/أول ثانية) يوقف التمرير، محدد ما عام.
   - فكرة واحدة، بلهجة وصوت brand.md (ودليل الشخصية لو موجود).
   - CTA واحد واضح.
   - لا حقائق أو أسعار مخترعة. ما تعرفه = سؤال لصاحب الحساب.
   - قيّم نفسك 1-10 (الخطاف، الصوت، الوضوح، الأصالة). أقل من 7 = أعد الكتابة.
3. احفظ كل منشور:
   ```bash
   python -m genx post-new <slug> - <<'JSON'
   {"plan": "2026-W45", "idea": "A", "pillar": "...", "format": "reel",
    "platforms": ["instagram", "tiktok", "facebook"],
    "hook": "...", "caption": "...", "hashtags": ["#..."], "cta": "...",
    "scheduled_for": "2026-11-03T20:00:00+03:00",
    "hypothesis": "لو ... فـ ... لأن ...",
    "production": {"tool": "magnific", "type": "image|video", "aspect": "4:5|9:16|1:1",
                   "prompt": "prompt إنجليزي مفصل: الموضوع، الإضاءة، الزاوية، الأسلوب، الألوان", "notes": "..."},
    "ai_label": false}
   JSON
   ```
   - منشور عميل: أضف `"client": "<الاسم>", "paid_disclosure": true`.
   - شخصية: الـ prompt يبدأ بوصف الشخصية الثابت من character.md حرفيًا.
4. `python -m genx submit <slug> <id>` لكل منشور. لو رُفض، اقرأ المخالفات، صحح بـ `post-edit`، وأعد submit.
5. لخّص لصاحب الحساب: كم منشور، وأي فكرة، وأي أسئلة. واقترح `/review`.
