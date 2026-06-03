CREATE TABLE IF NOT EXISTS seats (
  id SERIAL PRIMARY KEY,
  show_id TEXT NOT NULL,
  seat_no TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'AVAILABLE',
  UNIQUE(show_id, seat_no)
);

CREATE TABLE IF NOT EXISTS reservations (
  id UUID PRIMARY KEY,
  user_ref TEXT NOT NULL,
  movie_id TEXT NOT NULL,
  show_id TEXT NOT NULL,
  seat_ids TEXT[] NOT NULL,
  status TEXT NOT NULL,
  expires_at TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS idempotency_keys (
  id SERIAL PRIMARY KEY,
  idem_key TEXT NOT NULL UNIQUE,
  endpoint TEXT NOT NULL,
  request_hash TEXT NOT NULL,
  response_json JSONB NOT NULL,
  status_code INT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS payments (
  id UUID PRIMARY KEY,
  reservation_id UUID NOT NULL,
  status TEXT NOT NULL,
  external_ref TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS event_log (
  id BIGSERIAL PRIMARY KEY,
  reservation_id UUID,
  event_type TEXT NOT NULL,
  details JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO seats (show_id, seat_no, status)
SELECT 'show-1', s, 'AVAILABLE'
FROM unnest(ARRAY['A1','A2','A3','A4','B1','B2','B3','B4']) s
ON CONFLICT DO NOTHING;