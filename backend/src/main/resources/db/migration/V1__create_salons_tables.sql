CREATE TABLE salons (
    id              BIGSERIAL PRIMARY KEY,
    name            VARCHAR(255) NOT NULL,
    address         VARCHAR(255) NOT NULL,
    district        VARCHAR(255) NOT NULL,
    phone           VARCHAR(255),
    website_url     VARCHAR(255),
    price_range     VARCHAR(255),
    rating          NUMERIC(3, 2),
    review_count    INTEGER,
    source          VARCHAR(255),
    external_id     VARCHAR(255),
    created_at      TIMESTAMP(6) WITHOUT TIME ZONE NOT NULL,
    updated_at      TIMESTAMP(6) WITHOUT TIME ZONE NOT NULL
);

CREATE INDEX idx_salons_district ON salons (district);
CREATE INDEX idx_salons_rating ON salons (rating);
CREATE INDEX idx_salons_name ON salons (name);

CREATE TABLE salon_services (
    salon_id        BIGINT NOT NULL,
    service         VARCHAR(255) NOT NULL,
    service_order   INTEGER NOT NULL,
    PRIMARY KEY (salon_id, service_order),
    CONSTRAINT fk_salon_services_salon FOREIGN KEY (salon_id) REFERENCES salons (id) ON DELETE CASCADE
);
