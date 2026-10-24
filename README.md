# Brandr Agent — مدير سوشيال ميديا مستقل

Agent يدير حساب (أو عدّة حسابات) من الألف للياء: **تحليل ← تعلّم ← تخطيط ← إنتاج ← جدولة ← نشر ← قياس**، وكل دورة يتحسّن فيها محتوى كل حساب على حدة.

## كيف يشتغل (دورة واحدة لكل حساب)
1. **Sync**: ينشر المنشورات المعتمدة اللي حان وقتها، ويسحب أرقام الأداء.
2. **Analyze & Learn**: agent محلل يقرأ الأداء ويعيد كتابة `playbook.md` (ما ينجح / ما يفشل / تجارب مفتوحة). هذي ذاكرة الحساب.
3. **Plan & Create**: agent مخطط يحفظ خطة الأسبوع، ويكتب المنشورات مع *hypothesis* لكل واحد وتجربة جديدة كل أسبوع.
4. **Quality gate**: كل منشور يمر على (أ) guardrails بالكود (كلمات ممنوعة، حد يومي، فاصل زمني، منع التكرار) و(ب) ناقد LLM بدرجة ≥ 7/10، وإلا يرجع للمخطط ليعدّله.

الحسابات معزولة: فشل حساب ما يوقف البقية. الاستقلالية يفرضها الكود مو الـ prompt.

## مستويات الاستقلالية (`autonomy` في profile.json)
| الوضع | السلوك |
|---|---|
| `draft` | كل شيء مسودة، أنت تراجع وتعتمد |
| `approval` (الافتراضي في القالب) | مسودات تنتظر `brandr approve` |
| `auto` | يعتمد وينشر لحاله بعد اجتياز البوابات |

منشورات Instagram بدون `media_url` تبقى مسودة (`needs_media`) حتى في وضع `auto`: الـ agent يكتب `media_brief`، والصورة/الفيديو يجي من خط الإنتاج عندك.

## التشغيل
```bash
pip install -e .
export ANTHROPIC_API_KEY=...
brandr init my-brand            # ينشئ data/my-brand/profile.json — عدّله
brandr run --account my-brand   # دورة واحدة
brandr daemon --every-minutes 60  # تشغيل مستمر لكل الحسابات
brandr status                   # المسودات والمجدول
brandr approve my-brand all     # أو id محدد
brandr metrics my-brand m.json  # استيراد أرقام يدويًا: {"<post_id>": {"likes": 10, "reach": 500}}
```
مثال profile جاهز في `accounts/example/profile.json`. متغيرات: `BRANDR_HOME`, `BRANDR_MODEL`, `BRANDR_THINKING_BUDGET` (0 يعطّل التفكير الموسّع), `BRANDR_PUBLISHER=dryrun|meta`.

## النشر
- `dryrun` (افتراضي): يكتب في `outbox.jsonl` بدون نشر فعلي.
- `meta`: Facebook Page + Instagram عبر Graph API. يحتاج `META_TOKEN_<SLUG>`, `META_PAGE_ID_<SLUG>`, `META_IG_ID_<SLUG>`.

## حالة الاختبار
`python3 -m unittest discover -s tests -t .` — 6 اختبارات للـ guardrails، وأوضاع الاستقلالية، والناقد، وحلقة النشر ثم التعلّم، وعزل الأخطاء (بنموذج مزيّف).
**لم يُختبر مقابل Anthropic API الحقيقي ولا Meta Graph API الحقيقي** من هذه البيئة. جرّب أول مرة بـ `dryrun` ووضع `approval`.

## التوسعة
TikTok/X/LinkedIn: أضف class بدالتي `publish` و`fetch_metrics` في `publishers.py`. Canva/Magnific لتوليد الميديا: يوصَّل مكان `media_brief` ← `media_url`.
