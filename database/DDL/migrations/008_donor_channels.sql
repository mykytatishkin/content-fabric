-- 008_donor_channels.sql
-- Replaces hardcoded `arr_data` from Yii Shorts_from_videoController.php
-- (3 entries: id_yt_acc 28/31/34) with DB-backed config.
--
-- The Yii structure was:
--   $arr_data[id_yt_acc] = {
--     donors: [{channel_id, channel_name}, ...],
--     lang, channel_id, channel_name, keywords
--   }
--
-- We split into 2 tables:
--   donor_channel_configs        — per-target-channel meta (1 row per id_yt_acc)
--   donor_channel_sources        — list of donor YT channels (N rows per config)
--
-- Apply:
--   mysql ... < 008_donor_channels.sql

CREATE TABLE IF NOT EXISTS donor_channel_configs (
  id INT UNSIGNED NOT NULL AUTO_INCREMENT,
  channel_id INT UNSIGNED NOT NULL COMMENT 'FK to platform_channels.id (target YouTube channel)',
  legacy_yii_acc_id INT UNSIGNED NULL COMMENT 'Original Yii youtube_account.id (28/31/34) for traceability',
  language VARCHAR(20) NOT NULL DEFAULT 'uk' COMMENT 'TTS language for narration',
  target_handle VARCHAR(255) NOT NULL COMMENT 'YouTube handle (@xobiATVUA, @babysmilevlog, @Новини_1)',
  target_name VARCHAR(255) NOT NULL COMMENT 'Display name (Хобі ATV UA, Baby Smile Vlog, ...)',
  keywords TEXT NOT NULL COMMENT 'comma-separated keywords for hashtag generation',
  enabled TINYINT(1) NOT NULL DEFAULT 1,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_legacy_yii_acc (legacy_yii_acc_id),
  INDEX idx_channel_id (channel_id),
  INDEX idx_enabled (enabled)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS donor_channel_sources (
  id INT UNSIGNED NOT NULL AUTO_INCREMENT,
  config_id INT UNSIGNED NOT NULL COMMENT 'FK to donor_channel_configs.id',
  yt_channel_id VARCHAR(64) NOT NULL COMMENT 'YouTube UC-id (UCGz5TPWPY4TdnK1Bug04thg)',
  yt_handle VARCHAR(255) NOT NULL COMMENT '@LikeNastya_Vlog, @KidsDianaShow, ...',
  enabled TINYINT(1) NOT NULL DEFAULT 1,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_config_donor (config_id, yt_channel_id),
  INDEX idx_config_id (config_id),
  CONSTRAINT fk_dcs_config FOREIGN KEY (config_id)
    REFERENCES donor_channel_configs (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Seed data: legacy Yii arr_data (28/31/34)
-- Note: channel_id values point to platform_channels.id; if your local IDs
-- differ from the Yii youtube_account.id, update via UPDATE statements after
-- this migration. The legacy_yii_acc_id column lets you trace mapping back.

INSERT IGNORE INTO donor_channel_configs (channel_id, legacy_yii_acc_id, language, target_handle, target_name, keywords)
VALUES
  -- id_yt_acc 28: Хобі ATV UA (квадроцикли)
  (28, 28, 'uk', '@xobiATVUA', 'Хобі ATV UA',
   'квадроцикл, квадроциклы, atv, утв, квадрик, offroad, оффроуд, бездоріжжя, грязьові покатушки, mud riding, mudding, cross country, atv adventure, екстрим, екстремальні покатушки, квадро тури, atv tours, квадротур, квадропробіг, полювання на квадроциклі, рибалка на квадроциклі, polaris, can-am, yamaha grizzly, honda atv, sport atv, utility atv, квадроциклы 4x4, 4x4 offroad, повний привід, мотовсюдихід, квадро тюнінг, atv tuning, лебідка atv, шини atv, грязьові шини, mud tires, atv accessories, захист квадроцикла, квадроекіп, мотошолом, мотозахист, позашляхові пригоди, offroad action, atv racing, гонки atv, квадро клуб, atv vlog, покатушки 2025, atv extreme, лісові покатушки, гори на квадроциклі, водні перешкоди atv, глибока грязь atv'),

  -- id_yt_acc 31: Baby Smile Vlog (дитячий)
  (31, 31, 'ru', '@babysmilevlog', 'Baby Smile Vlog',
   'дети, детский канал, детские видео, малыш, малыши, детское развлечение, игры для детей, детский юмор, детские игры, детское шоу, семья, семейный канал, детские песни, детские сказки, обучающие видео, развивающие видео, развивающие игры, учим цвета, учим цифры, детские истории, мультики, детская анимация, детские игрушки, обзор игрушек, играем вместе, дошкольники, раннее развитие, детские приключения, детский смех, детский контент, детские занятия, веселые дети, смешные дети, детские танцы, песни для детей, сказки на ночь, творческие игры, детские поделки, развлечение для детей, детское обучение'),

  -- id_yt_acc 34: Новини UA
  (34, 34, 'uk', '@Новини_1', 'Новини',
   'новини україни, новини сьогодні, останні новини, українські новини, головні новини, хроніка подій, війна в україні, політика україни, економіка україни, новини онлайн, термінові новини, оперативні новини, новини україна зараз, ситуація в україні, новини києва, новини львова, новини одеси, новини харкова, актуальні новини, день новин, гарячі новини, щоденні новини, короткі новини, стрічка новин, топ новини дня, новини тижня, розслідування, аналітика, фактчек, новини суспільства, новини світу, новини європи, новини сша, міжнародні новини, міжнародна політика, новини нато, новини фронту, міжнародні події, міжнародний огляд, короткі новини україна, новина за 60 секунд, терміново україна, головне за день');

-- Seed donor sources for each config
-- 28: 1 donor channel
INSERT IGNORE INTO donor_channel_sources (config_id, yt_channel_id, yt_handle)
SELECT c.id, 'UCGz5TPWPY4TdnK1Bug04thg', '@xobiATVUA' FROM donor_channel_configs c WHERE c.legacy_yii_acc_id = 28;

-- 31: 6 donor channels (children's content)
INSERT IGNORE INTO donor_channel_sources (config_id, yt_channel_id, yt_handle)
SELECT c.id, 'UCJplp5SjeGSdVdwsfb9Q7lQ', '@LikeNastya_Vlog' FROM donor_channel_configs c WHERE c.legacy_yii_acc_id = 31;
INSERT IGNORE INTO donor_channel_sources (config_id, yt_channel_id, yt_handle)
SELECT c.id, 'UCx790OVgpTC1UVBQIqu3gnQ', '@KidsDianaShow' FROM donor_channel_configs c WHERE c.legacy_yii_acc_id = 31;
INSERT IGNORE INTO donor_channel_sources (config_id, yt_channel_id, yt_handle)
SELECT c.id, 'UCk8GzjMOrta8yxDcKfylJYw', '@KidsRomaShow' FROM donor_channel_configs c WHERE c.legacy_yii_acc_id = 31;
INSERT IGNORE INTO donor_channel_sources (config_id, yt_channel_id, yt_handle)
SELECT c.id, 'UCP9MW9ATjUwwulqEYTbp-Mw', '@VladandNiki' FROM donor_channel_configs c WHERE c.legacy_yii_acc_id = 31;
INSERT IGNORE INTO donor_channel_sources (config_id, yt_channel_id, yt_handle)
SELECT c.id, 'UC_8PAD0Qmi6_gpe77S1Atgg', '@MrMaxLife' FROM donor_channel_configs c WHERE c.legacy_yii_acc_id = 31;
INSERT IGNORE INTO donor_channel_sources (config_id, yt_channel_id, yt_handle)
SELECT c.id, 'UCcartHVtvAUzfajflyeT_Gg', '@misskaty1133' FROM donor_channel_configs c WHERE c.legacy_yii_acc_id = 31;

-- 34: 4 donor channels (Ukrainian news)
INSERT IGNORE INTO donor_channel_sources (config_id, yt_channel_id, yt_handle)
SELECT c.id, 'UCkyrSWEcjZKpIwMxiPfOcgg', '@5channel' FROM donor_channel_configs c WHERE c.legacy_yii_acc_id = 34;
INSERT IGNORE INTO donor_channel_sources (config_id, yt_channel_id, yt_handle)
SELECT c.id, 'UCKCVeAihEfJr-pGH7B73Wyg', '@unian' FROM donor_channel_configs c WHERE c.legacy_yii_acc_id = 34;
INSERT IGNORE INTO donor_channel_sources (config_id, yt_channel_id, yt_handle)
SELECT c.id, 'UCjAg2-3PgoksLAkYE88S_6g', '@UKRAINETODAY24' FROM donor_channel_configs c WHERE c.legacy_yii_acc_id = 34;
INSERT IGNORE INTO donor_channel_sources (config_id, yt_channel_id, yt_handle)
SELECT c.id, 'UChparf_xrUZ_CJGQY5g4aEg', '@УкраїнськаПравда' FROM donor_channel_configs c WHERE c.legacy_yii_acc_id = 34;

INSERT IGNORE INTO platform_schema_migrations (version, applied_at)
VALUES ('008_donor_channels', NOW());
