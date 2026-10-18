-- Esquema real de la capa Silver en PostgreSQL.
-- Generado automáticamente por data-lake/scripts/esquema.py
-- al final de cada ejecución de main.py. No editar a mano.

--
-- PostgreSQL database dump
--

\restrict silverschema

-- Dumped from database version 17.11 (Debian 17.11-1.pgdg13+2)
-- Dumped by pg_dump version 18.6

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: silver_etl_runs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.silver_etl_runs (
    run_id bigint NOT NULL,
    dataset_name text NOT NULL,
    target_table text NOT NULL,
    started_at timestamp with time zone NOT NULL,
    finished_at timestamp with time zone,
    status text NOT NULL,
    source_rows bigint,
    loaded_rows bigint,
    error_message text,
    CONSTRAINT silver_etl_runs_status_check CHECK ((status = ANY (ARRAY['RUNNING'::text, 'SUCCESS'::text, 'FAILED'::text])))
);


--
-- Name: TABLE silver_etl_runs; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.silver_etl_runs IS 'Capa Silver: bitácora de ejecuciones del ETL.';


--
-- Name: silver_etl_runs_run_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.silver_etl_runs_run_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: silver_etl_runs_run_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.silver_etl_runs_run_id_seq OWNED BY public.silver_etl_runs.run_id;


--
-- Name: silver_listings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.silver_listings (
    snapshot_id text NOT NULL,
    source_file text,
    id bigint NOT NULL,
    listing_url text,
    scrape_id bigint,
    last_scraped date,
    source text,
    name text,
    description text,
    neighborhood_overview text,
    picture_url text,
    host_id bigint,
    host_url text,
    host_profile_id bigint,
    host_profile_url text,
    host_name text,
    host_since text,
    hosts_time_as_user_years bigint,
    hosts_time_as_user_months bigint,
    hosts_time_as_host_years bigint,
    hosts_time_as_host_months bigint,
    host_location text,
    host_about text,
    host_response_time text,
    host_response_rate text,
    host_acceptance_rate text,
    host_is_superhost boolean,
    host_thumbnail_url text,
    host_picture_url text,
    host_neighbourhood text,
    host_listings_count bigint,
    host_total_listings_count text,
    host_verifications text,
    host_has_profile_pic boolean,
    host_identity_verified boolean,
    neighbourhood text,
    neighbourhood_cleansed text,
    neighbourhood_group_cleansed text,
    latitude numeric,
    longitude numeric,
    property_type text,
    room_type text,
    accommodates bigint,
    bathrooms numeric,
    bathrooms_text text,
    bedrooms bigint,
    beds bigint,
    amenities jsonb,
    price numeric,
    price_quote_checkin_date date,
    price_quote_checkout_date date,
    price_quote_total_price numeric,
    price_quote_price_per_night numeric,
    price_quote_raw jsonb,
    minimum_nights bigint,
    maximum_nights bigint,
    minimum_minimum_nights bigint,
    maximum_minimum_nights bigint,
    minimum_maximum_nights bigint,
    maximum_maximum_nights bigint,
    minimum_nights_avg_ntm numeric,
    maximum_nights_avg_ntm numeric,
    calendar_updated text,
    has_availability boolean,
    availability_30 bigint,
    availability_60 bigint,
    availability_90 bigint,
    availability_365 bigint,
    calendar_last_scraped date,
    number_of_reviews bigint,
    number_of_reviews_ltm bigint,
    number_of_reviews_l30d bigint,
    availability_eoy bigint,
    number_of_reviews_ly bigint,
    estimated_occupancy_l365d bigint,
    estimated_revenue_l365d bigint,
    first_review date,
    last_review date,
    review_scores_rating numeric,
    review_scores_accuracy numeric,
    review_scores_cleanliness numeric,
    review_scores_checkin numeric,
    review_scores_communication numeric,
    review_scores_location numeric,
    review_scores_value numeric,
    license text,
    instant_bookable text,
    calculated_host_listings_count bigint,
    calculated_host_listings_count_entire_homes bigint,
    calculated_host_listings_count_private_rooms bigint,
    calculated_host_listings_count_shared_rooms bigint,
    reviews_per_month numeric
);


--
-- Name: TABLE silver_listings; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.silver_listings IS 'Capa Silver: alojamientos por snapshot.';


--
-- Name: silver_neighbourhood_geometries; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.silver_neighbourhood_geometries (
    snapshot_id text NOT NULL,
    source_file text,
    neighbourhood text NOT NULL,
    neighbourhood_group text,
    geometry_type text,
    geometry jsonb
);


--
-- Name: TABLE silver_neighbourhood_geometries; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.silver_neighbourhood_geometries IS 'Capa Silver: geometrías de barrios por snapshot.';


--
-- Name: silver_neighbourhoods; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.silver_neighbourhoods (
    snapshot_id text NOT NULL,
    source_file text,
    neighbourhood_group text,
    neighbourhood text NOT NULL
);


--
-- Name: TABLE silver_neighbourhoods; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.silver_neighbourhoods IS 'Capa Silver: catálogo de barrios por snapshot.';


--
-- Name: silver_reviews; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.silver_reviews (
    snapshot_id text NOT NULL,
    source_file text,
    listing_id bigint,
    id bigint NOT NULL,
    date date,
    reviewer_id bigint,
    reviewer_name text,
    comments text
);


--
-- Name: TABLE silver_reviews; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.silver_reviews IS 'Capa Silver: reseñas por snapshot.';


--
-- Name: silver_etl_runs run_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.silver_etl_runs ALTER COLUMN run_id SET DEFAULT nextval('public.silver_etl_runs_run_id_seq'::regclass);


--
-- Name: silver_etl_runs silver_etl_runs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.silver_etl_runs
    ADD CONSTRAINT silver_etl_runs_pkey PRIMARY KEY (run_id);


--
-- Name: silver_listings silver_listings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.silver_listings
    ADD CONSTRAINT silver_listings_pkey PRIMARY KEY (snapshot_id, id);


--
-- Name: silver_neighbourhood_geometries silver_neighbourhood_geometries_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.silver_neighbourhood_geometries
    ADD CONSTRAINT silver_neighbourhood_geometries_pkey PRIMARY KEY (snapshot_id, neighbourhood);


--
-- Name: silver_neighbourhoods silver_neighbourhoods_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.silver_neighbourhoods
    ADD CONSTRAINT silver_neighbourhoods_pkey PRIMARY KEY (snapshot_id, neighbourhood);


--
-- Name: silver_reviews silver_reviews_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.silver_reviews
    ADD CONSTRAINT silver_reviews_pkey PRIMARY KEY (snapshot_id, id);


--
-- PostgreSQL database dump complete
--

\unrestrict silverschema

