-- 演示数据：用于在 Web Chat 中测试 company-call-analytics 技能。
-- 数据范围为 2026-08-13 至 2026-08-19，包含今天和明天。

INSERT OR IGNORE INTO companies (id, name)
VALUES (1, '星河科技');

INSERT OR IGNORE INTO phone_numbers (id, company_id, number, label)
VALUES
    (1, 1, '13800000001', '销售热线'),
    (2, 1, '13800000002', '客服热线');

INSERT OR IGNORE INTO call_records
    (id, company_id, phone_number_id, started_at, direction, duration_seconds, status)
VALUES
    (1, 1, 1, '2026-08-18T09:00:00+08:00', 'outbound', 180, 'completed'),
    (2, 1, 1, '2026-08-18T10:00:00+08:00', 'inbound', 240, 'completed'),
    (3, 1, 2, '2026-08-18T11:00:00+08:00', 'inbound', 120, 'completed'),
    (4, 1, 1, '2026-08-18T12:00:00+08:00', 'inbound', 0, 'missed'),
    (5, 1, 1, '2026-08-13T09:00:00+08:00', 'outbound', 180, 'completed'),
    (6, 1, 1, '2026-08-13T10:00:00+08:00', 'outbound', 210, 'completed'),
    (7, 1, 1, '2026-08-13T11:00:00+08:00', 'inbound', 150, 'completed'),
    (8, 1, 1, '2026-08-13T14:00:00+08:00', 'inbound', 90, 'completed'),
    (9, 1, 2, '2026-08-13T15:00:00+08:00', 'inbound', 120, 'completed'),
    (10, 1, 2, '2026-08-13T16:00:00+08:00', 'outbound', 100, 'completed'),
    (11, 1, 1, '2026-08-14T09:30:00+08:00', 'inbound', 240, 'completed'),
    (12, 1, 1, '2026-08-14T13:00:00+08:00', 'outbound', 180, 'completed'),
    (13, 1, 2, '2026-08-14T10:00:00+08:00', 'inbound', 120, 'completed'),
    (14, 1, 2, '2026-08-14T11:00:00+08:00', 'inbound', 130, 'completed'),
    (15, 1, 2, '2026-08-14T15:00:00+08:00', 'outbound', 160, 'completed'),
    (16, 1, 1, '2026-08-15T09:00:00+08:00', 'outbound', 180, 'completed'),
    (17, 1, 1, '2026-08-15T10:00:00+08:00', 'outbound', 190, 'completed'),
    (18, 1, 1, '2026-08-15T11:00:00+08:00', 'inbound', 200, 'completed'),
    (19, 1, 1, '2026-08-15T13:00:00+08:00', 'inbound', 160, 'completed'),
    (20, 1, 1, '2026-08-15T14:00:00+08:00', 'inbound', 140, 'completed'),
    (21, 1, 2, '2026-08-15T15:00:00+08:00', 'outbound', 120, 'completed'),
    (22, 1, 2, '2026-08-15T16:00:00+08:00', 'inbound', 0, 'missed'),
    (23, 1, 1, '2026-08-16T09:00:00+08:00', 'inbound', 180, 'completed'),
    (24, 1, 2, '2026-08-16T10:00:00+08:00', 'inbound', 120, 'completed'),
    (25, 1, 2, '2026-08-16T11:00:00+08:00', 'inbound', 140, 'completed'),
    (26, 1, 2, '2026-08-16T13:00:00+08:00', 'outbound', 160, 'completed'),
    (27, 1, 2, '2026-08-16T15:00:00+08:00', 'outbound', 180, 'completed'),
    (28, 1, 1, '2026-08-17T09:00:00+08:00', 'outbound', 180, 'completed'),
    (29, 1, 1, '2026-08-17T10:00:00+08:00', 'inbound', 150, 'completed'),
    (30, 1, 1, '2026-08-17T11:00:00+08:00', 'inbound', 130, 'completed'),
    (31, 1, 2, '2026-08-17T13:00:00+08:00', 'outbound', 120, 'completed'),
    (32, 1, 2, '2026-08-17T14:00:00+08:00', 'inbound', 140, 'completed'),
    (33, 1, 2, '2026-08-17T15:00:00+08:00', 'inbound', 0, 'cancelled'),
    (34, 1, 1, '2026-08-19T09:00:00+08:00', 'outbound', 180, 'completed'),
    (35, 1, 1, '2026-08-19T10:00:00+08:00', 'outbound', 190, 'completed'),
    (36, 1, 1, '2026-08-19T11:00:00+08:00', 'inbound', 200, 'completed'),
    (37, 1, 1, '2026-08-19T13:00:00+08:00', 'inbound', 160, 'completed'),
    (38, 1, 1, '2026-08-19T14:00:00+08:00', 'inbound', 140, 'completed'),
    (39, 1, 1, '2026-08-19T15:00:00+08:00', 'outbound', 120, 'completed'),
    (40, 1, 2, '2026-08-19T16:00:00+08:00', 'inbound', 120, 'completed'),
    (41, 1, 2, '2026-08-19T17:00:00+08:00', 'outbound', 140, 'completed');
