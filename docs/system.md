# تصميم نظام Genx Studio

آخر تحديث: 2026-11-01. يشرح كيف يشتغل النظام ولماذا، بناءً على بحث في طريقة عمل وكالات السوشيال ميديا، وتشغيل حسابات الـ AI influencers، وأنظمة الـ agents.

## ما يقوله البحث (والقرار المبني عليه)

| ما وجدناه | القرار في النظام |
| --- | --- |
| الوكالات تمشي بمراحل ثابتة: استراتيجية ← إنتاج ← مراجعة داخلية ← موافقة العميل ← جدولة ← قياس، وكل مرحلة لها مالك وحالة واضحة | دورة حياة المنشور بحالات يفرضها الكود (`genx/posts.py`)، وصاحب الحساب بوابة القرار |
| أنظمة الـ agents الناجحة تقسم الأدوار (بحث، كتابة، مراجعة، نشر، تحليل) مع موافقة بشرية قبل أي نشر، والتحليل يغذي البحث | الأدوار الستة في CLAUDE.md، والمحلل يحدّث playbook والبحث |
| تحليل المنافسين: تصنيف أفضل منشوراتهم حسب الخطاف والصيغة والموضوع، ومقارنة كل منشور بمعدل حسابه نفسه، ومكتبة خطافات مصنفة | `/research`: جمع عبر Apify، كشف المنشورات المتفوقة (≥ 2× الوسيط)، مكتبة خطافات (`swipe`) |
| حسابات الـ AI: أكبر مشكلة ثبات الشكل؛ الحل تثبيت الهوية مبكرًا بمراجع ووصف ثابت لكل توليد، ونشر منتظم 3-5 مرات في الأسبوع | `character_prompt` و`reference_images` في config، والإنتاج يوقف لو ما في مراجع معتمدة |
| الدخل الأكبر للـ AI influencers من صفقات البراندات، لكن أغلب الحسابات ما بتجيب دخل يذكر | الدخل يُتتبع لكل حساب (`revenue`)، وما نبني الخطة على دخل المنصات المباشر |
| الحساب الجديد: الفيديو القصير هو اللي يوصل لغير المتابعين، والخوارزمية في تيك توك تقيّم كل فيديو لحاله، ومعدل إكمال المشاهدة والخطاف في أول ثواني هم الأهم | مرحلة `launch` بخطة إطلاق، وأولوية الفيديو، والخطاف حقل إجباري |
| السلاسل المتكررة والمواعيد الثابتة تبني عادة عند الجمهور | `series` لكل حساب، والتقرير يقارن بينها |
| التفاعل هو «عملة» الخوارزمية | `/community`: ردود في أول ساعة، واستفسارات تتسجل كعملاء محتملين |
| النشر الآلي: انستغرام يحتاج حساب Business/Creator وصفحة فيسبوك وموافقة تطبيق من ميتا؛ تيك توك يقيّد النشر عبر API لحسابات خاصة حتى يجتاز التطبيق تدقيقهم | النشر يدوي بحزم جاهزة حاليًا، والحسابات تتسجل Business/Creator من أول يوم عشان الأتمتة لاحقًا |
| وسم المحتوى الواقعي المولّد بالـ AI مطلوب في تيك توك، وميتا تضع وسوم وتختبر وسم «AI Creator» على مستوى الحساب | `ai_label_required` للشخصيات الواقعية، والكود يرفض المنشور بدونه |

⚠️ أغلب المصادر مدونات شركات أدوات، فالأرقام فيها (نسب النمو، أسعار الصفقات) غير موثقة ولم نعتمد عليها. سياسات المنصات تتغير: نراجع المصادر الرسمية (Meta Business Help Center، إرشادات تيك توك) قبل أي أتمتة.

## البنية

```
طبقة المحفظة (portfolio/)        ← أرقام مجمّعة فقط، قرارات صاحب المحفظة
        │
 ┌──────┼──────┐
حساب   حساب   حساب                 ← كل حساب مشروع معزول (accounts/<slug>/)
 │
 ├─ الهوية: config.json, brand.md, ideas.md, character.md, community.md, launch.md
 ├─ المعرفة: research/ (منافسين، منشورات، خطافات، research.md), playbook.md
 ├─ التشغيل: plans/, posts/, media/
 └─ السجلات: decisions.md, snapshots.jsonl, leads.jsonl, revenue.jsonl
```

## الحلقة

بحث ← خطة (موافقة) ← كتابة + ناقد ← قواعد الكود ← مراجعة (موافقة) ← إنتاج ← نشر ← ردود ومجتمع ← أرقام ونمو ← تعلّم (playbook) ← بحث

## لسه ما اتبنى
1. لوحة القيادة (عرض كل الحسابات وقائمة القرارات).
2. التشغيل المجدول (دورة أسبوعية وتذكير يومي).
3. النشر وسحب الأرقام آليًا (بعد فتح الحسابات كـ Business، وموافقات المنصات، أو ربط Windsor.ai).

## المصادر
- [Sked Social: agency social media workflow](https://skedsocial.com/blog/agency-social-media-workflow)
- [Metricool: social media workflow 2026](https://metricool.com/social-media-workflow/)
- [Fast.io: AI agent social media automation](https://fast.io/resources/ai-agent-social-media-automation/)
- [Sprout Social insights: AI agents](https://sproutsocial.com/insights/?p=220377)
- [Cotera: tracking competitor social strategy](https://cotera.co/articles/how-to-track-competitor-social-media-strategy.md)
- [SociaVault: competitor swipe file](https://sociavault.com/blog/competitor-swipe-file-automate-creative-collection)
- [OpenArt: how to make AI influencers](https://openart.ai/blog/how-to-make-ai-influencers/)
- [Higgsfield: how to create an AI influencer](https://higgsfield.ai/academy/how-to-use/how-to-create-ai-influencer)
- [Oakgen: AI influencer monetization](https://oakgen.ai/blog/ai-influencer-monetization-guide)
- [Socialync: TikTok algorithm tips for new accounts 2026](https://www.socialync.io/blog/tiktok-algorithm-tips-new-accounts-2026)
- [Meta: Instagram content publishing docs](https://developers.facebook.com/documentation/instagram-platform/content-publishing)
- [Postiz docs: TikTok provider](https://docs.postiz.com/self-host/providers/tiktok)
- [Metricool: how to label AI content](https://metricool.com/how-to-label-ai-content/)
- [Cinerads: TikTok AI content policy 2026](https://www.cinerads.com/blog/tiktok-ai-content-policy)
