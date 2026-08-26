/**
 * MedGraphRAG Frontend — API Type Definitions
 * Single source of truth derived from backend/API_DOCUMENTATION.md
 */

// ============================================================================
// 1. System Health
// ============================================================================
export interface HealthComponents {
  retrieval: string;
  graph: string;
  llm_loaded: boolean;
}

export interface HealthResponse {
  status: string;
  components: HealthComponents;
  version: string;
}

// ============================================================================
// 2. Authentication & User Sessions
// ============================================================================
export interface LoginRequest {
  username?: string;
  password?: string;
}

export interface TokenResponse {
  token: string;
  token_type: string;
  user_id: string;
  ephemeral: boolean;
}

export interface UserClaims {
  user_id: string;
  role: 'user' | 'admin' | 'guest' | string;
  ephemeral: boolean;
  expires_in_minutes: number;
}

export interface LogoutResponse {
  status: string;
  user_id: string;
  guest_store_purged: boolean;
}

// ============================================================================
// 3. Query RAG Engine
// ============================================================================
export interface QueryRequest {
  query: string;
  destination?: string;
  attached_scan_id?: string;
}

export interface CitationMeta {
  label: string;
  chunk_id: string;
  document_id: string;
  source: string;
  category: string;
  chunk_type?: string;
  title?: string | null;
  snippet: string;
  fused_score: number;
  source_type: 'faiss' | 'graph' | 'both' | string;
}

export interface LatencyBreakdown {
  router?: number;
  retrieval?: number;
  context?: number;
  llm?: number;
  verification?: number;
  total: number;
}

export type AnswerStatus = 
  | 'verified'
  | 'caution'
  | 'uncertain'
  | 'contradiction_detected'
  | 'refusal'
  | 'out_of_scope'
  | 'error';

export type ConfidenceTier = 'high' | 'medium' | 'low';

export interface QueryResponse {
  route: 'medical_query' | 'knowledge_graph' | 'report' | 'out_of_scope' | string;
  answer_text: string;
  answer_status: AnswerStatus;
  confidence_tier: ConfidenceTier;
  final_confidence: number;
  citations: CitationMeta[];
  graph_paths: string[];
  disclaimer_present: boolean;
  retry_count: number;
  latency_breakdown: LatencyBreakdown;
  error?: string;
  detail?: string;
}

// ============================================================================
// 4. Diagnostic Report Interpretation & History
// ============================================================================
export interface ReportSummaryItem {
  report_id: string;
  report_date: string;
  filename: string;
  n_lab_values: number;
  critical_flag: boolean;
}

export interface LabValueDetailItem {
  test_name: string;
  value: number;
  unit: string;
  ref_low?: number | null;
  ref_high?: number | null;
  is_critical: boolean;
}

export interface ReportDetailResponse {
  report_id: string;
  report_date: string;
  filename: string;
  lab_values: LabValueDetailItem[];
}

export type ReportResponse = QueryResponse;

// ============================================================================
// 5. Feature 1: MedTrend Schemas
// ============================================================================
export type TrendDirection = 'worsening' | 'improving' | 'stable' | 'new' | 'resolved';

export interface LabMeasurement {
  report_id: string;
  report_date: string;
  value: number;
  unit: string;
  ref_low?: number | null;
  ref_high?: number | null;
  is_critical: boolean;
}

export interface GraphCausePath {
  test_name: string;
  disease_name: string;
  edge_type: string;
  graph_path_str: string;
}

export interface TrendItem {
  test_name: string;
  canonical_unit: string;
  measurements: LabMeasurement[];
  measurement_count: number;
  earliest_date?: string | null;
  latest_date?: string | null;
  earliest_value?: number | null;
  latest_value?: number | null;
  delta?: number | null;
  rate_per_month?: number | null;
  direction: TrendDirection;
  is_significant: boolean;
  significance_reason?: string | null;
  possible_causes: GraphCausePath[];
  clinical_framing: string;
}

export interface TrendResult {
  user_id: string;
  trends: TrendItem[];
  significant_count: number;
  summary_text: string;
  provenance: string[];
  disclaimer: string;
  disclaimer_present: boolean;
}

// ============================================================================
// 6. Feature 2: CareGap Schemas
// ============================================================================
export type GapType = 'out_of_target' | 'missing_recommended_check';

export interface GuidelineCitation {
  document_id: string;
  source: string;
  snippet: string;
  category?: string;
  fused_score?: number;
}

export interface GapItem {
  gap_type: GapType;
  condition_or_topic: string;
  recommended_check: string;
  observed_value?: string | null;
  guideline_target: string;
  status: string;
  guideline_provenance: GuidelineCitation[];
  recommendation_text: string;
}

export interface CareGapResult {
  user_id: string;
  report_id?: string | null;
  gaps: GapItem[];
  total_gaps: number;
  out_of_target_count: number;
  missing_check_count: number;
  summary_text: string;
  provenance: string[];
  disclaimer: string;
  disclaimer_present: boolean;
}

// ============================================================================
// 7. Feature 3: Evidence Coverage Map Schemas
// ============================================================================
export type CoverageClass = 'strong' | 'partial' | 'none';

export interface SubQuestionCoverage {
  sub_question: string;
  coverage_class: CoverageClass;
  top_fused_score: number;
  distinct_doc_count: number;
  evidence_count: number;
  top_citations: string[];
  suggested_rephrase?: string | null;
}

export interface CoverageMap {
  query: string;
  sub_questions: SubQuestionCoverage[];
  overall_coverage: CoverageClass;
  strong_count: number;
  partial_count: number;
  none_count: number;
  suggested_rephrases: string[];
  disclaimer: string;
  disclaimer_present: boolean;
}

export interface CoverageRequest {
  query: string;
}

// ============================================================================
// 8. API Error Envelope
// ============================================================================
export interface ApiError {
  status: number;
  message: string;
  detail?: string | { error?: string; detail?: string };
}

// ============================================================================
// 9. Multimodal Medical Imaging Schemas
// ============================================================================
export type ImageModality =
  | 'xray'
  | 'ct'
  | 'mri'
  | 'ultrasound'
  | 'pathology'
  | 'dermatology'
  | 'oct'
  | 'fundus'
  | 'endoscopy'
  | 'unknown';

export type ImageOrientation =
  | 'AP'
  | 'PA'
  | 'LATERAL'
  | 'OBLIQUE'
  | 'AXIAL'
  | 'CORONAL'
  | 'SAGITTAL'
  | 'UNKNOWN';

export interface VisualFinding {
  label: string;
  confidence: number;
  negated: boolean;
  location?: string | null;
  severity?: string | null;
  auc_reference?: number | null;
}

export interface MatchedReport {
  report_id: string;
  section: string;
  text_snippet: string;
}

export interface KnowledgeGraphPath {
  source_image_id: string;
  finding_label: string;
  finding_negated: boolean;
  matched_reports: MatchedReport[];
}

export interface ImageAnalysisResult {
  image_id: string;
  filename: string;
  modality: ImageModality;
  orientation: ImageOrientation;
  body_part?: string | null;
  mode: 'triage' | 'full';
  findings: string[];
  findings_detailed: VisualFinding[];
  impression: string;
  recommendations: string[];
  confidence_scores: Record<string, number>;
  refusal_tier: 'ANSWERED' | 'HEDGED' | 'REFUSED';
  has_graph_links: boolean;
  graph_paths: KnowledgeGraphPath[];
  graph_notice?: string | null;
  preview_url: string;
  processing_time_ms: number;
  model_used: string;
  provenance: string[];
  created_at: string;
}

export interface MultimodalCapabilities {
  image_formats: string[];
  dicom_support: boolean;
  pdf_support: boolean;
  biomedclip_triage: boolean;
  vlm_analysis: boolean;
  vlm_model: string;
  report_graph_links: boolean;
  private_encryption: string;
}

export interface MultimodalStatusResponse {
  service: string;
  version: string;
  capabilities: MultimodalCapabilities;
  supported_modalities: ImageModality[];
}
