-- Рекомендации ветеринара в записи визита: какие свойства нужны (diet_tags) и каких ингредиентов избегать (diet_exclude)
ALTER TABLE props ADD COLUMN IF NOT EXISTS diet_tags TEXT[] NOT NULL DEFAULT '{}';
ALTER TABLE props ADD COLUMN IF NOT EXISTS diet_exclude TEXT[] NOT NULL DEFAULT '{}';

-- Справочник пород: размер и предрасположенности (теги — те же, что у товаров)
CREATE TABLE IF NOT EXISTS breeds (
    id      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    species TEXT NOT NULL CHECK (species IN ('cat', 'dog')),
    name    TEXT NOT NULL,
    names   TEXT[] NOT NULL,  -- варианты написания в нижнем регистре, по ним ищется pets.breed
    size    TEXT NOT NULL CHECK (size IN ('small', 'medium', 'large')),
    tags    TEXT[] NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS breeds_names_idx ON breeds USING GIN (names);

-- Каталог для рекомендаций. Пустой массив в species/age_groups/sizes — подходит всем
CREATE TABLE IF NOT EXISTS products (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    kind        TEXT NOT NULL CHECK (kind IN ('food', 'toy', 'accessory', 'care')),
    name        TEXT NOT NULL,
    description TEXT,
    species     TEXT[] NOT NULL DEFAULT '{}',
    age_groups  TEXT[] NOT NULL DEFAULT '{}',
    sizes       TEXT[] NOT NULL DEFAULT '{}',
    tags        TEXT[] NOT NULL DEFAULT '{}',
    ingredients TEXT[] NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS products_kind_idx ON products (kind);

INSERT INTO breeds (species, name, names, size, tags) VALUES
    ('cat', 'Британская короткошёрстная', '{британская,британская короткошерстная,британская короткошёрстная,британец,british shorthair}', 'medium', '{weight_control,joint}'),
    ('cat', 'Шотландская вислоухая', '{шотландская,шотландская вислоухая,скоттиш фолд,scottish fold}', 'medium', '{joint,weight_control}'),
    ('cat', 'Мейн-кун', '{мейн-кун,мейн кун,мейнкун,maine coon}', 'large', '{joint,hairball,long_coat}'),
    ('cat', 'Персидская', '{персидская,перс,persian}', 'medium', '{hairball,long_coat,brachycephalic}'),
    ('cat', 'Сфинкс', '{сфинкс,канадский сфинкс,донской сфинкс,sphynx}', 'medium', '{skin_coat,sensitive_digestion}'),
    ('cat', 'Сиамская', '{сиамская,siamese}', 'small', '{active,dental}'),
    ('cat', 'Бенгальская', '{бенгальская,бенгал,bengal}', 'medium', '{active,intellectual}'),
    ('dog', 'Лабрадор-ретривер', '{лабрадор,лабрадор-ретривер,labrador}', 'large', '{weight_control,joint,chewer,active}'),
    ('dog', 'Немецкая овчарка', '{немецкая овчарка,овчарка,german shepherd}', 'large', '{joint,sensitive_digestion,active,intellectual}'),
    ('dog', 'Мопс', '{мопс,pug}', 'small', '{brachycephalic,weight_control,skin_coat}'),
    ('dog', 'Французский бульдог', '{французский бульдог,француз,french bulldog}', 'small', '{brachycephalic,hypoallergenic,skin_coat}'),
    ('dog', 'Йоркширский терьер', '{йоркширский терьер,йорк,yorkshire terrier}', 'small', '{dental,long_coat}'),
    ('dog', 'Чихуахуа', '{чихуахуа,chihuahua}', 'small', '{dental}'),
    ('dog', 'Хаски', '{хаски,сибирский хаски,husky}', 'large', '{active,intellectual,long_coat}'),
    ('dog', 'Корги', '{корги,вельш-корги,welsh corgi}', 'medium', '{weight_control,joint,active}'),
    ('dog', 'Бордер-колли', '{бордер-колли,бордер колли,border collie}', 'medium', '{active,intellectual}');

INSERT INTO products (kind, name, description, species, age_groups, sizes, tags, ingredients) VALUES
    -- корма для кошек
    ('food', 'Корм для котят с курицей', 'Полнорационный сухой корм для котят до года', '{cat}', '{baby}', '{}', '{}', '{chicken,grain}'),
    ('food', 'Корм для взрослых кошек с индейкой', 'Повседневный сухой корм', '{cat}', '{adult}', '{}', '{}', '{turkey,grain}'),
    ('food', 'Корм для стерилизованных кошек', 'Пониженная калорийность, контроль веса', '{cat}', '{adult,senior}', '{}', '{weight_control,sterilised,urinary}', '{chicken,grain}'),
    ('food', 'Гипоаллергенный корм с ягнёнком для кошек', 'Один источник белка, без злаков', '{cat}', '{adult,senior}', '{}', '{hypoallergenic,skin_coat}', '{lamb}'),
    ('food', 'Корм для кошек с чувствительным пищеварением', 'Легкоусвояемый, с пребиотиками', '{cat}', '{adult,senior}', '{}', '{sensitive_digestion}', '{turkey,rice}'),
    ('food', 'Корм для вывода шерсти', 'Клетчатка для вывода комков шерсти', '{cat}', '{adult,senior}', '{}', '{hairball,skin_coat}', '{chicken,grain}'),
    ('food', 'Корм для пожилых кошек с рыбой', 'Поддержка почек и суставов после 10 лет', '{cat}', '{senior}', '{}', '{renal,joint}', '{fish,rice}'),
    ('food', 'Корм для профилактики мочекаменной болезни', 'Контроль минерального состава мочи', '{cat}', '{adult,senior}', '{}', '{urinary}', '{fish,rice}'),
    ('food', 'Корм для крупных кошек', 'Крупная гранула, поддержка суставов', '{cat}', '{adult}', '{}', '{joint}', '{chicken,fish}'),
    -- корма для собак
    ('food', 'Корм для щенков с курицей', 'Для щенков до года', '{dog}', '{baby}', '{}', '{}', '{chicken,grain}'),
    ('food', 'Корм для щенков крупных пород', 'Контроль роста и поддержка суставов', '{dog}', '{baby}', '{large}', '{joint}', '{chicken,rice}'),
    ('food', 'Корм для взрослых собак мелких пород', 'Мелкая гранула, чистит зубы', '{dog}', '{adult}', '{small}', '{dental}', '{chicken,rice}'),
    ('food', 'Корм для взрослых собак средних пород с говядиной', 'Повседневный сухой корм', '{dog}', '{adult}', '{medium}', '{}', '{beef,grain}'),
    ('food', 'Корм для взрослых собак крупных пород', 'Поддержка суставов, крупная гранула', '{dog}', '{adult}', '{large}', '{joint}', '{chicken,grain}'),
    ('food', 'Корм для собак с контролем веса', 'Пониженная калорийность, L-карнитин', '{dog}', '{adult,senior}', '{}', '{weight_control}', '{turkey,rice}'),
    ('food', 'Гипоаллергенный корм с ягнёнком для собак', 'Один источник белка, без злаков', '{dog}', '{adult,senior}', '{}', '{hypoallergenic,skin_coat}', '{lamb}'),
    ('food', 'Корм с лососем для чувствительного пищеварения', 'Легкоусвояемый, без курицы', '{dog}', '{adult,senior}', '{}', '{sensitive_digestion,skin_coat}', '{fish,rice}'),
    ('food', 'Корм для брахицефалов', 'Гранула удобной формы для коротких морд', '{dog}', '{adult}', '{small}', '{brachycephalic}', '{chicken,rice}'),
    ('food', 'Корм для пожилых собак', 'Поддержка суставов и почек', '{dog}', '{senior}', '{}', '{joint,renal}', '{chicken,rice}'),
    -- игрушки
    ('toy', 'Удочка с пёрышками', 'Охотничья игра вместе с хозяином', '{cat}', '{}', '{}', '{active,weight_control}', '{}'),
    ('toy', 'Интерактивный трек с мячиками', 'Игра без хозяина', '{cat}', '{baby,adult}', '{}', '{active}', '{}'),
    ('toy', 'Кормушка-головоломка для кошек', 'Корм достаётся через задачку, замедляет поедание', '{cat}', '{}', '{}', '{intellectual,weight_control}', '{}'),
    ('toy', 'Мышка с кошачьей мятой', 'Спокойная игра', '{cat}', '{}', '{}', '{}', '{}'),
    ('toy', 'Прочная жевательная игрушка', 'Каучук для собак, которые всё грызут', '{dog}', '{adult}', '{medium,large}', '{chewer,dental}', '{}'),
    ('toy', 'Мягкая игрушка для щенков', 'Для периода смены зубов', '{dog}', '{baby}', '{}', '{chewer}', '{}'),
    ('toy', 'Мяч-апорт', 'Активные игры на прогулке', '{dog}', '{baby,adult}', '{}', '{active,weight_control}', '{}'),
    ('toy', 'Нюхательный коврик', 'Поиск лакомств, нагрузка для мозга', '{dog}', '{}', '{}', '{intellectual}', '{}'),
    ('toy', 'Головоломка для собак', 'Развивающая игра с лакомствами', '{dog}', '{adult,senior}', '{}', '{intellectual}', '{}'),
    ('toy', 'Канат для перетягивания', 'Игра с хозяином, чистит зубы', '{dog}', '{adult}', '{small,medium}', '{dental,active}', '{}'),
    -- аксессуары
    ('accessory', 'Высокая когтеточка-домик', 'Место для лазания и отдыха', '{cat}', '{}', '{}', '{active}', '{}'),
    ('accessory', 'Миска-кормушка с замедлением', 'Против быстрого поедания и переедания', '{}', '{}', '{}', '{weight_control}', '{}'),
    ('accessory', 'Широкая неглубокая миска', 'Удобно есть животным с короткой мордой', '{}', '{}', '{}', '{brachycephalic}', '{}'),
    ('accessory', 'Ортопедический лежак', 'Снимает нагрузку с суставов', '{}', '{senior}', '{}', '{joint}', '{}'),
    ('accessory', 'Шлейка вместо ошейника', 'Не давит на горло при прогулке', '{dog}', '{}', '{small}', '{brachycephalic}', '{}'),
    ('accessory', 'Поилка-фонтан', 'Побуждает пить больше воды', '{cat}', '{}', '{}', '{urinary,renal}', '{}'),
    -- уход
    ('care', 'Пуходёрка для длинной шерсти', 'Вычёсывание колтунов', '{}', '{}', '{}', '{long_coat,hairball}', '{}'),
    ('care', 'Фурминатор для подшёрстка', 'В период линьки', '{}', '{}', '{}', '{long_coat}', '{}'),
    ('care', 'Зубная щётка и паста для животных', 'Профилактика зубного камня', '{}', '{}', '{}', '{dental}', '{}'),
    ('care', 'Мягкий шампунь для чувствительной кожи', 'Без отдушек', '{}', '{}', '{}', '{skin_coat,hypoallergenic}', '{}'),
    ('care', 'Лосьон для складок на морде', 'Уход за складками у брахицефалов', '{}', '{}', '{}', '{brachycephalic,skin_coat}', '{}'),
    ('care', 'Когтерез', 'Для регулярной стрижки когтей', '{}', '{}', '{}', '{}', '{}');
