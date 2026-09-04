-- PostgreSQL + pgvector schema for quantum collision literature
-- Run: psql -d yourdb -f db_setup.sql

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE papers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_pdf TEXT NOT NULL,
    
    -- Paper metadata
    title TEXT,
    authors JSONB,
    journal TEXT,
    year INT,
    doi TEXT,
    keywords TEXT[],
    
    -- Structured content
    research JSONB NOT NULL,
    states JSONB NOT NULL,
    theory JSONB NOT NULL,
    numerical JSONB NOT NULL,
    observables JSONB NOT NULL,
    results JSONB NOT NULL,
    figures JSONB NOT NULL,
    equations JSONB NOT NULL,
    limitations JSONB NOT NULL,
    references JSONB NOT NULL,
    
    -- Embeddings for RAG
    embedding vector(1536),
    
    -- Full text for keyword search
    full_text TEXT,
    
    meta JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for structured queries
CREATE INDEX idx_papers_system ON papers USING GIN ((research->'system'));
CREATE INDEX idx_papers_method ON papers USING GIN ((theory->'method'));
CREATE INDEX idx_papers_observables ON papers USING GIN (observables);
CREATE INDEX idx_papers_potential ON papers USING GIN ((theory->'potential'));
CREATE INDEX idx_papers_year ON papers (year);
CREATE INDEX idx_papers_journal ON papers (journal);

-- Vector index for semantic search
CREATE INDEX idx_papers_embedding ON papers USING hnsw (embedding vector_cosine_ops);

-- Full-text search
ALTER TABLE papers ADD COLUMN tsv tsvector GENERATED ALWAYS AS (
    to_tsvector('english', coalesce(title,'') || ' ' || 
        coalesce(research->>'research_question','') || ' ' ||
        coalesce(theory->>'method','') || ' ' ||
        coalesce(full_text,'')
    )
) STORED;
CREATE INDEX idx_papers_fts ON papers USING GIN (tsv);

-- Function for hybrid search
CREATE OR REPLACE FUNCTION hybrid_search(
    query_text TEXT,
    query_embedding vector(1536),
    filter_json JSONB DEFAULT '{}',
    top_k INT DEFAULT 10,
    vector_weight FLOAT DEFAULT 0.7,
    text_weight FLOAT DEFAULT 0.3
) RETURNS TABLE (
    id UUID,
    title TEXT,
    year INT,
    research JSONB,
    theory JSONB,
    observables JSONB,
    results JSONB,
    score FLOAT
) LANGUAGE sql AS $$
    SELECT
        p.id,
        p.title,
        p.year,
        p.research,
        p.theory,
        p.observables,
        p.results,
        (vector_weight * (1 - (p.embedding <=> query_embedding)) + 
         text_weight * ts_rank_cd(p.tsv, plainto_tsquery('english', query_text))) AS score
    FROM papers p
    WHERE (filter_json = '{}'::jsonb OR p.research @> filter_json OR p.theory @> filter_json OR p.observables @> filter_json)
    ORDER BY score DESC
    LIMIT top_k;
$$;