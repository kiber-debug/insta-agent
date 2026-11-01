# Instagram цитата-агент — ишга тушириш (код ёзиш шарт эмас)

Агент ҳар куни ўзи: цитата топади → фактчек қилади → расм ясайди → Instagram'га чиқаради.
Ҳаммаси GitHub'да бепул ишлайди, компьютерингизда Python керак эмас.

## Калитлар (Telegram керак эмас)
1. **ANTHROPIC_API_KEY** — console.anthropic.com → API Keys → Create key (ҳисобга бироз пул қўйиш керак).
2. **IMGBB_KEY** — api.imgbb.com → бепул рўйхатдан ўтиб, API key олинг (расмга ҳавола учун).
3. **GEMINI_API_KEY** (олим расмини яратиш учун) — aistudio.google.com → Get API key.
   Ўрнига **OPENAI_API_KEY** ҳам бўлади (platform.openai.com). Расм яратиш пуллик бўлиши мумкин, нархини ўша сайтда текширинг.
   Иккаласини ҳам қўймасангиз, агент тайёр тоғ манзараси фонида чиқаради (бу бепул).
4. **IG_USER_ID ва IG_ACCESS_TOKEN** (Instagram учун, энг мураккаб қисм — pastda).

## GitHub'га жойлаш
1. github.com'да рўйхатдан ўтинг → New repository (Private) → ном: insta-agent.
2. "uploading an existing file" орқали шу папкадаги ҳамма файлни (`.github` папкаси билан) юкланг.
3. Repo → Settings → Secrets and variables → Actions:
   - **Secrets** бўлимига юқоридаги калитларни қўшинг (номлари ўзгармасин).
   - **Variables** бўлимига: `BLOG_HANDLE` (масалан @mening_blogim), керак бўлса `POST_LANGUAGE`, `BLOG_NICHE`.
4. Actions → "Instagram агент" → Run workflow. 1-2 дақиқадан сўнг ишга тушиш саҳифасининг пастида **posts** (Artifacts) пайдо бўлади: уни юклаб олиб, тайёр расм ва матнни кўрасиз.

## Хавфсиз бошланг
Дастлаб `MODE` қўйилмаган, яъни **preview**: агент фақат расм ва матн тайёрлайди (юқоридаги posts архивида кўрасиз), Instagram'га чиқармайди. 1-2 ҳафта сифатини кўринг.
Яхши бўлса: Settings → Variables → `MODE` = `publish` — шундан кейин ўзи чиқара бошлайди.

## Instagram'ни улаш (publish учун)
1. Instagram аккаунтни **Business** ёки **Creator**га ўтказинг.
2. Facebook саҳифа очиб, Instagram'ни унга уланг.
3. developers.facebook.com → My Apps → Create App (Business) → "Instagram Graph API" қўшинг.
4. Graph API Explorer'да токен олинг, рухсатлар: `instagram_basic`, `instagram_content_publish`, `pages_show_list`, `pages_read_engagement`.
5. Токенни "узоқ муддатли" (long-lived, ~60 кун) қилинг ва IG_USER_ID'ни `me/accounts` → саҳифа → `instagram_business_account` орқали топинг.
6. Токен ~60 кунда тугайди, янгилаб туриш керак.

Шу 4–6 қадамда тиқилиб қолсангиз, айтинг, скриншот билан бирга ёрдам бераман.

## Тил ва дизайн
- Асосий дизайн (эталон): чапда муаллифнинг қиёфаси ва соҳасига мос фон, ўнгда цитата (калит сўзлар олтин рангда), муаллиф ва касби. Расмни Gemini/OpenAI яратади, ёзувларни агент ўзи қўяди (шунда хато чиқмайди).
- Қиёфасиз вариант: GitHub Variables'да `SUBJECT` = `symbolic` қилсангиз, одамсиз рамзий манзара (тоғ, маёқ, кўчат) чиқади.
- Расм калити бўлмаса ёки генерация ишламаса, агент ўзи 4 хил ранг мавзусидаги тоғ манзарасини чизади (тонг, тунги осмон, яшил шафақ, бинафша шафақ).
- Ўлчам: `LAYOUT` = `portrait` (Instagram 4:5, одатдаги) ёки `landscape` (16:9). Иккаласида ҳам одам чапда, ёзув ўнгда.
- Тил: `POST_LANGUAGE` (Variables). Лотин ёзуви учун замонавий Poppins шрифти, кирилл учун Lora ишлатилади.
- Дизайн: 4 хил ранг мавзуси навбатма-навбат алмашади (қора/олтин, оч/тўқ сариқ, кўк/мента, яшил/шафақ). `agent.py` ичидаги `THEMES` рўйхатидан ўзгартирса бўлади.

## Вақтни ўзгартириш
`.github/workflows/post.yml` ичида `cron: "0 5 * * *"` (UTC). Тошкент = UTC+5.
