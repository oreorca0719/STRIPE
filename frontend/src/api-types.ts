/* eslint-disable */
// 자동 생성 — 손으로 고치지 않는다.
// 단일 진실 공급원: backend/app/schemas/ (서버 스키마). 다시 만들기: backend 에서
//   python -m app.schemas.typescript
// 서버 스키마와 다르면 backend/tests/test_api_types.py 가 실패한다.

/** A4(음절/초) 분포. 타당성 범위 안의 값만 구간에 넣는다. */
export interface A4Distribution {
  bin_width: number;
  range_min: number;
  range_max: number;
  /** range_min 부터 bin_width 폭 구간별 회차 수 */
  bin_counts: number[];
  in_range_count: number;
  out_of_range_count: number;
  /** 음절/초. 값이 없으면 null */
  percentiles: Percentiles | null;
}

/** 세션 종합 정답률 분포 (0~1 을 같은 폭으로). */
export interface AccuracyDistribution {
  /** 0~1 을 len(bin_counts) 등분한 구간별 세션 수 */
  bin_counts: number[];
  session_count: number;
  /** 비율 0~1. 값이 없으면 null */
  percentiles: Percentiles | null;
}

export interface ActiveUpdate {
  is_active: boolean;
}

/** 적응형 판단 — 다음 회차로 가는가, 여기서 끝내는가. */
export type AdaptiveAction = "continue" | "stop"

/**
 * 방금 끝난 회차 뒤의 행동.
 *
 * 계속이면 다음 난도·장르가 있고, 종료면 영점 난도와 신뢰도가 있다.
 * 한쪽의 칸이 다른 쪽에 섞이면 거부한다.
 */
export interface AdaptiveDecision {
  /** continue=다음 회차, stop=종료 */
  action: AdaptiveAction;
  /** 이 판단 뒤 세션 상태 */
  status: DiagSessionStatus;
  /** 종료 시 영점 난도 */
  anchor_difficulty: Difficulty | null;
  /** 종료 시 측정 신뢰도 */
  reliability_flag: ReliabilityFlag | null;
  /** 계속 시 다음 난도 */
  next_difficulty: Difficulty | null;
  /** 계속 시 다음 장르 */
  next_genre: TextGenre | null;
}

/**
 * 관리자 계정 발급. 비밀번호는 서버가 임시값으로 만들어 응답에 1회 반환한다.
 *
 * must_change_password 를 발급 시점에 정하는 이유: 파일럿 학생 계정은
 * 변경 화면에서 이탈하지 않도록 False 로 발급한다(STR-90). 교사·학부모 등
 * 일반 발급은 기본값 True 로 최초 로그인 시 변경을 강제한다.
 */
export interface AdminUserCreate {
  username: string;
  name: string;
  role?: UserRole;
  grade?: GradeLevel | null;
  must_change_password?: boolean;
}

/** 정렬에서 어긋난 원문 위치. 계산 가능성만 제공한다 — 오독 유형을 단정하지 않는다. */
export interface AlignmentDeviations {
  /** 대치(S) */
  substitution_positions: number[];
  /** 생략(D) */
  deletion_positions: number[];
  /** 첨가(I) — 이 원문 위치 앞에 끼어들었다 */
  insertion_positions: number[];
}

/** 60초에 걸린 회차만 접두부 정렬이다(계약 ⑤, 변경 금지). */
export type AlignmentMode = "global" | "prefix_global"

/** 문항 하나에 고른 답. 선지 수 이내인지·그 회차 지문의 문항인지는 서버가 DB 로 확인한다. */
export interface AnswerSubmit {
  /** diagnosis_rounds.id */
  round_id: number;
  /** questions.id — 그 회차 지문의 문항이어야 한다 */
  question_id: number;
  /** 고른 선지 번호 */
  student_answer: number;
  /** 문항을 보고 고르기까지 ms. 안 쟀으면 null */
  response_time_ms?: number | null;
}

export interface AppInfo {
  name: string;
  env: string;
  llm_configured: boolean;
  llm_model: string | null;
  stt_configured: boolean;
}

export interface AreaAccuracy {
  area: TargetArea;
  correct_count: number;
  question_count: number;
  /** 문항이 없으면 null */
  accuracy: number | null;
}

/** 화면에 보내는 영역 집계 — 정답률을 서버가 계산해 붙였다. */
export interface AreaTallyView {
  /** 독해 영역 */
  area: TargetArea;
  /** 맞힌 문항 수 */
  correct_count: number;
  /** 푼 문항 수 */
  question_count: number;
  /** 정답률 0~1. 문항이 없으면 null */
  accuracy: number | null;
}

/** 영역 × 장르 한 칸의 정답률. 문항이 없던 칸은 null(측정 안 함). */
export interface AreaView {
  /** 독해 영역 */
  area: TargetArea;
  /** 지문 장르 */
  genre: TextGenre;
  /** 정답률 0~1. 문항이 없던 칸은 null */
  accuracy: number | null;
}

/** 읽는 동안 화면이 가려지거나 돌아온 순간. */
export interface AwayEvent {
  /** hidden=가려짐, visible=돌아옴 */
  type: AwayEventType;
  /** 읽기 시작 버튼부터 경과한 ms */
  at_ms: number;
}

/** 읽는 동안 화면이 가려졌다·돌아왔다 (visibilitychange). */
export type AwayEventType = "hidden" | "visible"

/** 한 Betts 수준의 회차 수와, 그 묶음 안에서의 비율(서버가 계산해 싣는다). */
export interface BettsCount {
  betts_level: BettsLevel;
  round_count: number;
  /** 이 묶음의 전체 회차 중 비율. 회차가 없으면 null */
  ratio: number | null;
}

export type BettsLevel = "independent" | "instructional" | "frustration"

export interface Body_measure_reading_time_api_audio_timing_post {
  /** 녹음 파일 (WAV/WebM) */
  audio: string;
}

export interface Body_transcribe_oral_reading_api_audio_oral_post {
  /** 음성 파일 (WAV, PCM) */
  audio: string;
  /** 원본 지문 텍스트 */
  original_text: string;
  /** 녹음 시작~끝(ms) — 묵독·음독 저장과 같은 단위 */
  reading_time_ms: number;
}

/** 무엇을 근거로 골랐나 — 가장 최근 판정. */
export interface BookBasis {
  session_id: number;
  label_5: Label5;
  prescription_group: PrescriptionGroup;
  /** 처방군·영점에서 나온 난도 범위 */
  difficulties: Difficulty[];
  interest_topics: string[];
  /** 완독 경험이 필요해 짧은 책을 먼저 낸다 */
  prefer_short: boolean;
}

/** 도서 난도를 무엇을 근거로 매겼나 (STR-108). */
export type BookDifficultySource = "publisher" | "curriculum_list" | "manual"

/** '책' 하면 드는 느낌 — 단일 진실 공급원: survey_questions.json student A-5 선지 */
export type BookImage = "boring" | "difficult" | "obligation" | "study" | "no_interest" | "fun" | "curious" | "helpful" | "enjoyable" | "other"

/** 추천 도서 한 권과 추천 사유. */
export interface BookRecommendation {
  id: number;
  isbn13: string | null;
  title: string;
  author: string | null;
  publisher: string | null;
  published_year: number | null;
  page_count: number | null;
  cover_url: string | null;
  description: string | null;
  genre: TextGenre;
  difficulty: Difficulty;
  topic_tags: string[];
  /** 관심 주제와 겹친 주제 — 추천 사유 */
  matched_topics: string[];
  difficulty_source: BookDifficultySource | null;
}

export interface BookRow {
  id: number;
  isbn13: string | null;
  title: string;
  author: string | null;
  publisher: string | null;
  published_year: number | null;
  page_count: number | null;
  grade_group: GradeGroup;
  genre: TextGenre;
  difficulty: Difficulty;
  topic_tags: string[];
  difficulty_source: BookDifficultySource | null;
  source: BookSource | null;
  review_status: ReviewStatus;
  is_active: boolean;
}

/** 도서 데이터의 출처. */
export type BookSource = "api" | "manual" | "curriculum_list" | "template"

export interface BooksCatalog {
  book_count: number;
  /** 승인되고 활성인 도서 */
  approved_count: number;
  /** 2 학년군 × 2 장르 × 3 난도 = 12칸 전부 */
  coverage: CoverageCell[];
  books: BookRow[];
}

/** 나에게 맞는 책. 비어 있으면 이유가 있다. */
export interface BooksForMe {
  books: BookRecommendation[];
  /** books 가 비었을 때만 있다 */
  reason: BooksUnavailableReason | null;
  catalog_empty: boolean;
  /** 판정·설문이 없으면 null */
  based_on: BookBasis | null;
}

/** '나에게 맞는 책'이 비어 있는 이유 — 화면 문구가 갈린다. */
export type BooksUnavailableReason = "no_diagnosis" | "no_profile" | "catalog_empty" | "no_match"

/** 다건 발급 결과. 임시 비밀번호가 여러 건 한 번에 나가므로 재조회 경로는 없다. */
export interface BulkIssued {
  grade: GradeLevel;
  count: number;
  credentials: IssuedCredential[];
}

/**
 * 파일럿 학생 계정 다건 발급 (STR-90).
 *
 * 아이디는 `{학년}-{일련번호 3자리}` 스키마로 자동 생성한다(elem5-017).
 * 학년 구분은 되면서 실명이 들어가지 않는 식별코드다. 실명을 받지 않으므로
 * 이름도 같은 값을 쓴다 — 식별코드↔학생 매핑표는 시스템 밖에서 관리한다.
 *
 * 학생 전용이다. 학년 기반 아이디 형식이 다른 역할에는 의미가 없다.
 */
export interface BulkUserCreate {
  grade: GradeLevel;
  start?: number;
  count: number;
  must_change_password?: boolean;
}

/**
 * 이은주(2026) 텍스트 선정 7원칙. 원칙마다 통과(true)·불통과(false)·미작성(null).
 *
 * 승인에는 7개 모두 true 여야 한다 — 검수 API 가 확인한다.
 */
export interface ChecklistInput {
  /** 배경지식 통제 */
  background_knowledge?: boolean | null;
  /** 문화 편향 배제 */
  cultural_bias?: boolean | null;
  /** 장르 충실 */
  genre_fit?: boolean | null;
  /** 학년 적정 어휘 */
  vocabulary_level?: boolean | null;
  /** 적정 길이 */
  text_length?: boolean | null;
  /** 독립성 */
  independence?: boolean | null;
  /** 중립성 */
  neutrality?: boolean | null;
}

/**
 * 이은주(2026) 텍스트 선정 7원칙. 원칙마다 통과(true)·불통과(false)·미작성(null).
 *
 * 승인에는 7개 모두 true 여야 한다 — 검수 API 가 확인한다.
 */
export interface Checklist {
  /** 배경지식 통제 */
  background_knowledge: boolean | null;
  /** 문화 편향 배제 */
  cultural_bias: boolean | null;
  /** 장르 충실 */
  genre_fit: boolean | null;
  /** 학년 적정 어휘 */
  vocabulary_level: boolean | null;
  /** 적정 길이 */
  text_length: boolean | null;
  /** 독립성 */
  independence: boolean | null;
  /** 중립성 */
  neutrality: boolean | null;
}

export interface ChecklistInfo {
  principles: Principle[];
  statuses: StatusLabel[];
  source: string;
}

/** 하나를 고른다 — 단일 선택·4/5/6점 척도. */
export interface ChoiceQuestion {
  code: string;
  block: number | null;
  status: QuestionStatus;
  text: string;
  storage_field: string | null;
  required: boolean;
  show_if: ShowIf | null;
  /** 가정환경 점수(B-3~B-6 합)에 들어가는 문항 */
  env_score: boolean;
  guide_text: string | null;
  usage_note: string[];
  storage_note: string[];
  options_note: string[];
  response_type: "single_select" | "scale_4" | "scale_5" | "scale_6";
  options: Option[];
}

/** 선택지 한 개 — 코드와 화면 문구. */
export interface CodeLabel {
  code: string;
  label: string;
}

/** 독해 — 판정 값을 그대로 옮긴다. */
export interface ComprehensionView {
  /** 독해 3단 수준 */
  level: Level3;
  /** 전체 정답률 0~1. 문항이 없으면 null */
  overall_accuracy: number | null;
  /** 6칸, 약점 프로필과 같은 순서 */
  areas: AreaView[];
}

/** 동의 확인 방법. 파일럿은 서면, 정식 오픈은 휴대전화 본인인증(STR-88). */
export type ConsentConfirmMethod = "written" | "phone_verification"

export interface ConsentListResponse {
  summary: ConsentSummary;
  items: ConsentRow[];
}

export interface ConsentRevoke {
  note?: string | null;
}

/**
 * 학생별 동의 현황. 기록이 없는 학생도 has_record=False 로 함께 내려준다 —
 * '아직 안 받은 사람'이 보이지 않으면 회수 누락을 발견할 수 없다.
 */
export interface ConsentRow {
  user_id: number;
  username: string;
  name: string;
  grade: GradeLevel | null;
  is_active: boolean;
  has_record: boolean;
  consent_id: number | null;
  confirm_method: ConsentConfirmMethod | null;
  consent_required: boolean | null;
  consent_optional: boolean | null;
  consented_at: string | null;
  document_location: string | null;
  revoked: boolean | null;
  revoked_at: string | null;
  recorded_by_name: string | null;
  note: string | null;
  /** 필수 동의가 있고 철회되지 않았다 */
  can_take_diagnosis: boolean;
}

/** 파기 직전의 동의 기록 사본. 동의 기록은 파기와 함께 지워지므로 옮겨 둔다. */
export interface ConsentSnapshot {
  confirm_method: ConsentConfirmMethod;
  consent_required: boolean;
  consent_optional: boolean;
  consented_at: string;
  document_location: string | null;
  revoked: boolean;
  revoked_at: string | null;
}

export interface ConsentSummary {
  student_count: number;
  /** 필수 동의 회수 완료(철회 안 됨) */
  collected_count: number;
  revoked_count: number;
  /** 기록 자체가 없음 */
  missing_count: number;
  /** 기록은 있으나 필수 동의 없음 */
  refused_count: number;
  /** REQUIRE_PILOT_CONSENT 현재 값 — 켜져 있으면 미동의 학생 응시 차단 */
  enforcement_on: boolean;
}

/** 회수 기록 등록·갱신. 학생 1명당 1건이므로 같은 학생에 다시 보내면 갱신된다. */
export interface ConsentUpsert {
  user_id: number;
  confirm_method?: ConsentConfirmMethod;
  consent_required?: boolean;
  consent_optional?: boolean;
  /** 미지정 시 서버 시각 */
  consented_at?: string | null;
  document_location?: string | null;
  note?: string | null;
}

/** 지문을 만든 주체. */
export type ContentAuthor = "jun" | "ai"

/** 학년군 × 장르 × 난도 한 칸의 승인·활성 도서 수. */
export interface CoverageCell {
  grade_group: GradeGroup;
  genre: TextGenre;
  difficulty: Difficulty;
  book_count: number;
}

/** 최초 로그인 시 아이디·비밀번호 변경. 현재 비밀번호로 본인 확인. */
export interface CredentialChange {
  username: string;
  current_password: string;
  new_username?: string | null;
  new_password: string;
}

export interface DatabaseInfo {
  ok: boolean;
  version: string | null;
  migration: string | null;
}

/**
 * 파기로 함께 사라진 행 수 — 대상 계정에서 CASCADE 로 지워지는 **모든** 테이블.
 *
 * 예전 기록은 처방(prescription_results)·보호자 설문(parent_responses)·
 * 보호자 연결(user_relations)을 세지 않았다. 지워지는데 기록에 없었다.
 * 칸 이름은 `{테이블}_count` 다. 그 셋은 2026-09-25 이전 기록에서 null 이다 — 0 이 아니라 "그때 세지 않음"(원칙 2).
 * 이후 기록은 항상 센다(disposal._counts).
 */
export interface DeletedCounts {
  student_profiles_count: number;
  parent_responses_count: number | null;
  diagnosis_sessions_count: number;
  diagnosis_rounds_count: number;
  question_responses_count: number;
  comprehension_results_count: number;
  fluency_results_count: number;
  judgment_results_count: number;
  prescription_results_count: number | null;
  reports_count: number;
  consent_records_count: number;
  user_relations_count: number | null;
}

/** 정보주체가 고르는 삭제 요청 사유 — 본인 관점. */
export type DeletionReason = "withdraw" | "privacy" | "mistake" | "other"

export interface DeletionReasons {
  reasons: CodeLabel[];
  backup_notice: string;
}

/** 삭제 요청 접수. 보호자가 자녀를 대신할 때만 대상을 지정한다. */
export interface DeletionRequestIn {
  subject_user_id?: number | null;
  reason: DeletionReason;
  note?: string | null;
}

export interface DeletionRequestList {
  items: DeletionRequestView[];
  pending_count: number;
}

/** 접수 직후 응답 — 처리방침의 백업 잔존 고지를 함께 싣는다(접수하는 순간 알려야 한다). */
export interface DeletionRequestReceipt {
  id: number;
  subject_user_id: number;
  subject_code: string;
  requester_code: string;
  requester_role: UserRole;
  reason: DeletionReason;
  reason_label: string;
  note: string | null;
  status: DeletionRequestStatus;
  requested_at: string;
  resolved_at: string | null;
  resolved_by_code: string | null;
  resolution_note: string | null;
  disposal_log_id: number | null;
  backup_notice: string;
}

export type DeletionRequestStatus = "pending" | "completed" | "rejected" | "cancelled"

/** 삭제 요청 한 건 — 요청자·관리자 화면 공통. */
export interface DeletionRequestView {
  id: number;
  subject_user_id: number;
  subject_code: string;
  requester_code: string;
  requester_role: UserRole;
  reason: DeletionReason;
  reason_label: string;
  note: string | null;
  status: DeletionRequestStatus;
  requested_at: string;
  resolved_at: string | null;
  resolved_by_code: string | null;
  resolution_note: string | null;
  disposal_log_id: number | null;
}

/** 배포 구성 설명 — 코드에 적힌 고정 문구. */
export interface DeploymentInfo {
  platform: string;
  runtime: string;
  tls: string;
  cicd: string;
  backup: string;
}

export type DiagSessionStatus = "in_progress" | "completed" | "early_stop" | "indeterminate" | "abandoned"

/** 진단 상세 — 세션·학생·판정·처방·리포트·회차. */
export interface DiagnosisDetail {
  session: SessionBrief;
  student: StudentBrief | null;
  judgment: JudgmentBrief | null;
  prescription: PrescriptionBrief | null;
  report: ReportBrief | null;
  rounds: RoundDetail[];
}

/** 진단 응시 목록 한 줄. 판정 전이면 판정 칸이 전부 null. */
export interface DiagnosisListItem {
  session_id: number;
  status: DiagSessionStatus;
  started_at: string | null;
  completed_at: string | null;
  round_count: number;
  student_id: number;
  student_name: string;
  username: string;
  label_5: Label5 | null;
  prescription_group: PrescriptionGroup | null;
  overall_accuracy: number | null;
  fluency_level: Level3 | null;
  comprehension_level: Level3 | null;
  correct_count: number | null;
  question_count: number | null;
}

export interface DiagnosisResultResponse {
  session: SessionResponse;
  rounds: RoundResponse[];
  fluency_results: FluencyResultResponse[];
  question_responses: QuestionResponseResult[];
}

export type Difficulty = "easy" | "normal" | "hard"

/** 난도 하나의 Betts 분포. */
export interface DifficultyRow {
  difficulty: Difficulty;
  round_count: number;
  /** Betts 3수준 전부 */
  betts: BettsCount[];
  mean_accuracy: number | null;
  mean_readability_score: number | null;
  by_grade_group: GradeGroupBetts[];
}

export interface DifficultyValidity {
  round_count: number;
  /** 회차 30개 이상이어야 판정을 믿을 수 있다 */
  sufficient_sample: boolean;
  /** 표본이 있는 난도만, easy→hard 순서 */
  by_difficulty: DifficultyRow[];
  /** 난도가 2종 이상 있어야 판정한다 */
  verdict: DifficultyVerdict | null;
}

/** easy 는 독립 비율이 높고 hard 는 좌절 비율이 높아야 라벨이 작동한다. */
export interface DifficultyVerdict {
  independent_decreasing: boolean;
  frustration_increasing: boolean;
  label_works: boolean;
  note: string;
}

/**
 * 면책 문구 코드. 리포트가 이 코드로 report_templates 에서 문구를 찾는다.
 *
 * **지금 목록은 구현 기준이다.** 계약(Package #4 S5-FN-04)은
 * basic·unstable·silent_only·early_stop·grade_boundary·fluency_unavailable 로
 * 서로 다르다 — 확정은 문준석 회신 대기(docs/모듈간_데이터_확정필요.md 1-1).
 * 자유 문자열이 아니라 여기 없는 코드는 저장 자체가 안 된다.
 */
export type DisclaimerCode = "basic" | "fluency_unavailable" | "fluency_implausible" | "fluency_partial_implausible" | "text_repeated" | "reliability_low" | "reliability_unstable"

/**
 * 면책 코드의 **집합**. 순서에 뜻이 없고 중복이 없다.
 *
 * 코드가 없으면 빈 목록이다. null 이 아니다 — null 은 "판정하지 않음"이다.
 */
export interface Disclaimers {
  /** 면책 코드. 중복 없이 enum 정의 순서 */
  codes: DisclaimerCode[];
}

export interface DisposalLogItem {
  id: number;
  subject_user_id: number;
  subject_code: string;
  subject_grade: GradeLevel | null;
  disposed_at: string;
  disposed_by_code: string | null;
  reason: DisposalReason;
  reason_label: string;
  note: string | null;
  deleted_counts: DeletedCounts;
  consent_snapshot: ConsentSnapshot | null;
}

/** 무엇이 지워지는지 — 실행 전 확인용. */
export interface DisposalPreview {
  user_id: number;
  code: string;
  name: string;
  role: UserRole;
  grade: GradeLevel | null;
  is_active: boolean;
  counts: DeletedCounts;
  consent: ConsentSnapshot | null;
  confirm_hint: string;
  warning: string;
}

/** 관리자 파기 사유 — 운영자 관점. */
export type DisposalReason = "retention_expired" | "subject_request" | "consent_revoked" | "pilot_closed" | "test_data" | "other"

/** 파기 실행 요청. 확인 문자열이 대상 아이디와 같아야 실행된다. */
export interface DisposalRequest {
  user_id: number;
  reason: DisposalReason;
  confirm_code: string;
  note?: string | null;
}

export interface DisposalResult {
  id: number;
  subject_code: string;
  disposed_at: string;
  reason: DisposalReason;
  reason_label: string;
  deleted_counts: DeletedCounts;
  /** 동의 기록 사본을 남겼나 */
  consent_preserved: boolean;
  /** 이 파기로 완료 처리된 삭제 요청 수 */
  linked_request_count: number;
}

export interface Distributions {
  a4: A4Distribution;
  accuracy: AccuracyDistribution;
  /** A5·A6·A7 3칸 전부 */
  area_accuracy: AreaAccuracy[];
}

export interface Dropoff {
  /** 세션 상태 5종 전부 */
  status_counts: StatusCount[];
  session_count: number;
  /** 끝난 세션(completed·early_stop·indeterminate) / 전체. 세션이 없으면 null */
  completion_ratio: number | null;
  incomplete_by_rounds_reached: RoundsReached[];
  incomplete_last_round_stage: LastRoundStage;
}

/**
 * 1회 진단 소요시간 (STR-112) — 보호자 동의서 문구의 근거.
 *
 * 예전에는 '과업 시간 = 묵독 + 문항 응답 시간'이라고 했지만, 문항 응답 시간
 * (response_time_ms)은 화면이 보낸 적이 없어 늘 null 이었고 그걸 0 으로 더했다.
 * 결과는 사실상 묵독 시간뿐이었다. 이제 잰 것만 이름대로 싣는다(원칙 2).
 */
export interface Duration {
  session_count: number;
  /** 세션 20개 이상이어야 동의서 문구로 쓸 수 있다 */
  sufficient_sample: boolean;
  /** 세션 시작~종료(분) */
  total_minutes: Percentiles | null;
  /** 세션별 묵독 시간 합(분) */
  reading_minutes: Percentiles | null;
  /** 응답 시간이 기록된 문항 응답 수. 0 이면 응답 시간은 재지 않은 것이다 */
  answer_time_measured_count: number;
}

export interface FinalizeResponse {
  judgment: JudgmentResultResponse;
  prescription: PrescriptionResultResponse;
}

export interface FluencyResultResponse {
  id: number;
  session_id: number;
  round_id: number;
  type: FluencyType;
  /** 두 버튼 사이 실제 시각 차이 */
  reading_time_ms: number;
  /** 묵독 자동성. 음독이면 null */
  a4_syllable_per_sec: number | null;
  /** 음독 — 감독자가 센 오류 수 */
  supervisor_error_count: number | null;
  /** 음독 자동 채점. 서버가 센 지문 음절 수(text_syllable_count)도 여기 있다 */
  oral_analysis: OralReadingAnalysis | null;
  created_at: string;
}

export type FluencySource = "oral" | "silent" | "unavailable"

export type FluencyType = "oral" | "silent"

export type FluencyUnit = "CWPM" | "SPS" | "none"

/** 유창성 — 판정 값을 그대로 옮긴다(변조 금지 §6). */
export interface FluencyView {
  /** 유창성 3단 수준 */
  level: Level3;
  /** 판정에 쓴 값인가. false 면 화면이 수치를 보여주지 않는다 */
  valid: boolean;
  value: number | null;
  /** SPS=음절/초, CWPM=음절/분, 값 없으면 none */
  value_unit: FluencyUnit;
}

export type Gender = "M" | "F" | "other"

/** 선호 글 종류 — 단일 진실 공급원: survey_questions.json student C-3 선지 */
export type GenrePreference = "story" | "comics" | "science_nature" | "history_society" | "sports" | "cooking_life" | "fantasy" | "mystery_horror" | "poem_essay" | "other"

export type GradeGroup = "G4_G6" | "G7"

export interface GradeGroupBetts {
  grade_group: GradeGroup;
  /** Betts 3수준 전부 */
  betts: BettsCount[];
}

/** 학년마다 척도 하나 — A-4 생애 독서 그래프. 배열의 위치가 곧 학년이다. */
export interface GradeHistoryQuestion {
  code: string;
  block: number | null;
  status: QuestionStatus;
  text: string;
  storage_field: string | null;
  required: boolean;
  show_if: ShowIf | null;
  /** 가정환경 점수(B-3~B-6 합)에 들어가는 문항 */
  env_score: boolean;
  guide_text: string | null;
  usage_note: string[];
  storage_note: string[];
  options_note: string[];
  response_type: "grade_history";
  grades: GradeSlot[];
  scale: ScalePoint[];
  /** 이 문항의 답(학년)보다 뒤 학년 칸은 비활성 */
  auto_disable_after: string | null;
}

export type GradeLevel = "elem1" | "elem2" | "elem3" | "elem4" | "elem5" | "elem6" | "mid1"

export interface GradeSlot {
  label: string;
  grade: number;
}

export interface HTTPValidationError {
  detail?: ValidationError[];
}

/** 살아 있는가 — 의존성을 보지 않는다. */
export interface Health {
  status: HealthStatus;
  env: string;
}

export type HealthStatus = "ok" | "degraded"

/** 선택 + 자유 입력 (예약 문항). */
export interface HybridQuestion {
  code: string;
  block: number | null;
  status: QuestionStatus;
  text: string;
  storage_field: string | null;
  required: boolean;
  show_if: ShowIf | null;
  /** 가정환경 점수(B-3~B-6 합)에 들어가는 문항 */
  env_score: boolean;
  guide_text: string | null;
  usage_note: string[];
  storage_note: string[];
  options_note: string[];
  response_type: "hybrid";
  options: Option[];
}

/** 계정 발급·비밀번호 초기화 응답. temp_password 는 이때만 평문으로 나간다. */
export interface IssuedCredential {
  user: UserResponse;
  temp_password: string;
}

export interface JudgmentBrief {
  label_5: Label5;
  prescription_group: PrescriptionGroup;
  matrix_position: string;
  fluency_level: Level3;
  fluency_value: number | null;
  fluency_value_unit: FluencyUnit;
  comprehension_level: Level3;
  overall_accuracy: number | null;
  correct_count: number;
  question_count: number;
  weakness_profile_12: WeaknessProfileView;
  metacognition: Metacognition | null;
  reliability_flag: ReliabilityFlag;
  disclaimer_flags: Disclaimers;
}

export interface JudgmentResultResponse {
  id: number;
  diagnosis_session_id: number;
  fluency_level: Level3;
  fluency_source: FluencySource;
  fluency_valid: boolean;
  fluency_value: number | null;
  fluency_value_unit: FluencyUnit;
  comprehension_level: Level3;
  overall_accuracy: number | null;
  correct_count: number;
  question_count: number;
  weakness_profile_12: WeaknessProfileView;
  matrix_position: string;
  label_5: Label5;
  prescription_group: PrescriptionGroup;
  anchor_difficulty: Difficulty | null;
  metacognition: Metacognition | null;
  /** 예측 − 실제, 문항 수 차이. 음수면 과소평가. 예측(D-2)이 없으면 null */
  metacognition_gap_count: number | null;
  /** 실제 정답률을 10문항 기준으로 환산한 정답 수 */
  actual_correct_count_of_10: number | null;
  reliability_flag: ReliabilityFlag;
  disclaimer_flags: Disclaimers;
}

export type Label5 = "excellent" | "observe" | "caution" | "risk" | "urgent"

export interface LabelCount {
  label_5: Label5;
  judgment_count: number;
}

/** 미완료 세션의 마지막 회차에서 어디까지 갔나. */
export interface LastRoundStage {
  /** 읽기 측정 전에 멈춤 */
  before_reading_count: number;
  /** 읽고 문항은 하나도 안 풂 */
  after_reading_no_answer_count: number;
  /** 문항을 풀다 멈춤 */
  partial_answers_count: number;
}

/** 법정 기재 사항 (STR-86). 비어 있는 항목이 missing 에 나온다. */
export interface LegalInfoView {
  org_name: string;
  org_representative: string;
  org_address: string;
  org_reg_no: string;
  officer_name: string;
  officer_title: string;
  officer_email: string;
  officer_phone: string;
  announced_on: string;
  effective_on: string;
  pilot_start_on: string;
  pilot_end_on: string;
  /** 보유 기간(개월) */
  retention_months: number;
  retention_until: string | null;
  missing: string[];
  publishable: boolean;
}

/** 유창성/독해 수준 3분할. */
export type Level3 = "low" | "mid" | "high"

export type Metacognition = "accurate" | "overestimate" | "underestimate"

/** 여러 개를 고른다. */
export interface MultiQuestion {
  code: string;
  block: number | null;
  status: QuestionStatus;
  text: string;
  storage_field: string | null;
  required: boolean;
  show_if: ShowIf | null;
  /** 가정환경 점수(B-3~B-6 합)에 들어가는 문항 */
  env_score: boolean;
  guide_text: string | null;
  usage_note: string[];
  storage_note: string[];
  options_note: string[];
  response_type: "multi_select";
  options: Option[];
  min_select_count: number | null;
  max_select_count: number | null;
  free_text_field: string | null;
}

export interface MyDeletionRequests {
  items: DeletionRequestView[];
  backup_notice: string;
}

/** 이력 목록 한 줄. 판정 전(미완료) 세션은 판정 칸이 전부 null. */
export interface MySessionItem {
  session_id: number;
  status: DiagSessionStatus;
  started_at: string | null;
  completed_at: string | null;
  round_count: number;
  label_5: Label5 | null;
  prescription_group: PrescriptionGroup | null;
  fluency_level: Level3 | null;
  fluency_valid: boolean | null;
  comprehension_level: Level3 | null;
  overall_accuracy: number | null;
  reliability_flag: ReliabilityFlag | null;
}

/** 학생 홈 요약. 진단 이력이 없으면 completed_count=0, latest=null. */
export interface MySummaryResponse {
  completed_count: number;
  /** 이어하기 배너용 */
  in_progress_session_id: number | null;
  latest: MySessionItem | null;
}

/** 책을 안 읽는 이유 — 단일 진실 공급원: survey_questions.json student A-6 선지 */
export type NonReadingReason = "not_fun" | "no_interest" | "forced" | "not_understood" | "other_activities" | "no_time" | "no_habit" | "other"

/** 숫자를 입력하거나 슬라이더로 고른다. */
export interface NumberQuestion {
  code: string;
  block: number | null;
  status: QuestionStatus;
  text: string;
  storage_field: string | null;
  required: boolean;
  show_if: ShowIf | null;
  /** 가정환경 점수(B-3~B-6 합)에 들어가는 문항 */
  env_score: boolean;
  guide_text: string | null;
  usage_note: string[];
  storage_note: string[];
  options_note: string[];
  response_type: "numeric_input" | "slider";
  min: number;
  max: number;
  step: number;
  unit: string | null;
}

/** 선지 한 개. value 가 저장값이고 순서와 무관하다(scale_direction 참조). */
export interface Option {
  label: string;
  /** 저장값 — 척도는 정수, 범주는 코드 문자열 */
  value: number | string;
  /** 고르면 자유 입력칸이 열린다 ('기타') */
  free_text: boolean;
}

/**
 * 음독 한 회차 (B안 — 시간 자동 + 오류 수 감독자 입력).
 *
 * 지문 음절 수는 받지 않는다 — 서버가 원문에서 센다. 보낸 값을 믿으면 분모를
 * 조작해 정확도를 올릴 수 있다.
 */
export interface OralFluencySubmit {
  session_id: number;
  /** 어느 지문을 읽었는지 */
  round_id: number;
  /** 녹음 시작~끝, 묵독과 같은 단위 */
  reading_time_ms: number;
  /** 감독자가 센 총 오류 수. B안의 기준값 */
  supervisor_error_count: number;
  transcript?: string | null;
}

/**
 * 음독 채점 한 건 (계약 패키지 #1 L3).
 *
 * A1 = scored_m ÷ (scored_time_ms / 60000)       음절/분
 * A2 = scored_m ÷ (scored_m + scored_s + scored_d)  첨가 제외
 */
export interface OralReadingAnalysis {
  scoring_rule_version: string;
  score_status: OralScoreStatus;
  score_unavailable_reason: OralUnscorableReason | null;
  a1_correct_syllables_per_minute: number | null;
  a2_target_syllable_accuracy: number | null;
  /** 일치 */
  scored_m: number | null;
  /** 대치 */
  scored_s: number | null;
  /** 생략 */
  scored_d: number | null;
  /** 첨가 */
  scored_i: number | null;
  /** 시도한 원문 음절 = M+S+D. 정렬 전이면 null */
  oral_syllable_count: number | null;
  alignment_deviations: AlignmentDeviations | null;
  /** 정렬이 소비한 접두부 끝 — 묵독 이어읽기 시작점 */
  continuation_source_offset: number | null;
  alignment_mode: AlignmentMode | null;
  /** 녹음 시작~끝(버튼·타임아웃 기준). VAD 로 대체하지 않는다 */
  scored_time_ms: number;
  text_syllable_count: number;
  quality_gate: QualityGate;
  /** 전사 음절 / 원문 음절. 1 을 넘을 수 있다(첨가·오인식) */
  transcript_length_ratio: number;
  /** 감독자가 직접 센 오류 수(B안) */
  supervisor_error_count: number | null;
  notes: string[];
}

/** 채점이 성립했는가. 사람이 센 회차의 자리는 기획 확인 대기(확정필요 1-4). */
export type OralScoreStatus = "scored" | "unscorable"

/** 전사와 대조 결과. 참고용이다 — 판정에 넣으려면 /fluency/oral 로 저장한다. */
export interface OralTranscription {
  stt_adapter: SttAdapterName;
  transcript: string;
  confidence_ratio: number | null;
  audio_duration_ms: number | null;
  analysis: OralReadingAnalysis;
}

export type OralUnscorableReason = "empty_transcript_unresolved" | "stt_unusable"

export interface OutlierItem {
  fluency_id: number;
  session_id: number;
  student: string;
  round_number: number | null;
  text_code: string | null;
  reading_time_ms: number;
  text_syllable_count: number | null;
  a4_syllable_per_sec: number;
  reason: OutlierReason;
}

/** A4 타당성 게이트에 걸린 이유. */
export type OutlierReason = "too_slow" | "too_fast"

export interface Outliers {
  range_min: number;
  range_max: number;
  item_count: number;
  items: OutlierItem[];
}

/** 대시보드 첫 줄. */
export interface Overview {
  student_count: number;
  teacher_count: number;
  /** 진단 세션 전체 */
  session_count: number;
  /** 끝난 세션 (completed·early_stop·indeterminate) */
  finished_session_count: number;
  approved_text_count: number;
  approved_question_count: number;
}

/** 보호자의 도서 선택 기준 — 단일 진실 공급원: survey_questions.json parent E-6 선지 */
export type ParentBookCriteria = "child_interest" | "curriculum" | "recommendation" | "bestseller" | "none" | "other"

/** 보호자가 참고하는 정보원 — 단일 진실 공급원: survey_questions.json parent E-5 선지 */
export type ParentInfoSource = "community" | "youtube" | "sns" | "teacher" | "library" | "other_parents" | "none" | "other"

/**
 * 보호자 설문 — 화면에 뜨는 문항의 저장 칸과 1:1.
 *
 * 전 문항 선택 사항이다. 보호자가 중간에 그만두어도 받아 두고, 덜 채워진
 * 응답은 환경 점수가 산출되지 않을 뿐 학생 진단을 막지 않는다.
 * 미응답은 0 이 아니라 null 이다.
 */
export interface ParentSurveyIn {
  /** 어느 진단의 응답인지. 자녀가 하나면 생략 가능 */
  profile_id?: number | null;
  parent_freq_estimate?: "1" | "2" | "3" | "4" | "5" | "6" | null;
  parent_reading_level?: "1" | "2" | "3" | "4" | "5" | null;
  /** E-3 자녀가 맞힐 것 같은 문항 수 (10문항 중) */
  parent_predicted_correct_count?: number | null;
  parent_recommend_freq?: "1" | "2" | "3" | "4" | null;
  parent_info_source?: ParentInfoSource | null;
  parent_book_criteria?: ParentBookCriteria | null;
  parent_reading_support?: "1" | "2" | "3" | "4" | null;
  books_at_home?: "1" | "2" | "3" | "4" | null;
  parent_reading_model?: "1" | "2" | "3" | "4" | null;
  bookstore_library_visits?: "1" | "2" | "3" | "4" | null;
}

export interface ParentSurveyOut {
  id: number;
  profile_id: number;
  /** 관리자 대리 입력(종이 회수분)이면 null */
  parent_user_id: number | null;
  parent_freq_estimate: "1" | "2" | "3" | "4" | "5" | "6" | null;
  parent_reading_level: "1" | "2" | "3" | "4" | "5" | null;
  parent_predicted_correct_count: number | null;
  parent_recommend_freq: "1" | "2" | "3" | "4" | null;
  parent_info_source: ParentInfoSource | null;
  parent_book_criteria: ParentBookCriteria | null;
  parent_reading_support: "1" | "2" | "3" | "4" | null;
  books_at_home: "1" | "2" | "3" | "4" | null;
  parent_reading_model: "1" | "2" | "3" | "4" | null;
  bookstore_library_visits: "1" | "2" | "3" | "4" | null;
  /** B-3~B-6 합 4~16. 넷 중 하나라도 비면 null */
  home_environment_score: number | null;
  created_at: string;
}

/** P33·P67 이 곧 판정 경계 후보(STR-15)다. 표본 수를 함께 싣는다. */
export interface Percentiles {
  sample_count: number;
  p33: number;
  p50: number;
  p67: number;
  min: number;
  max: number;
}

export interface PrescriptionBrief {
  prescription_type: PrescriptionType;
  type_tone: ToneCode;
  recommended_texts: RecommendedTexts;
  weakness_training_plan: TrainingPlan | null;
}

export type PrescriptionGroup = "G1" | "G2" | "G3" | "G4" | "G5" | "G6"

export interface PrescriptionResultResponse {
  id: number;
  judgment_id: number;
  prescription_type: PrescriptionType;
  recommended_texts: RecommendedTexts;
  weakness_training_plan: TrainingPlan | null;
  type_tone: ToneCode;
  next_session_difficulty: Difficulty | null;
}

export type PrescriptionType = "A_only" | "B_only" | "A_and_B" | "basic_intervention"

export interface Principle {
  key: string;
  label: string;
  desc: string;
}

/**
 * 학생 설문 — 화면에 뜨는 문항(active·conditional)의 저장 칸과 1:1.
 *
 * 칸 이름 = 문항의 storage_field. 값의 범위·개수는 설문 파일에서 만든다.
 * 예약 문항(reserved)은 받지 않는다 — 보내면 모르는 키로 거부된다.
 *
 * 조건부 2문항(A-5·A-6)은 비독자로 판정된 학생에게만 뜬다. 그 외 학생은 null —
 * '해당 없음'이지 '무응답'이 아니다.
 */
export interface ProfileCreate {
  /** B-1 학년 (7=중1) */
  grade: "4" | "5" | "6" | "7";
  /** B-2 */
  gender?: Gender | null;
  /** A-2 독서 빈도, 클수록 자주 */
  reading_freq?: "1" | "2" | "3" | "4" | "5" | "6" | null;
  /** A-3 독서 태도, 클수록 좋아함 */
  reading_attitude?: "1" | "2" | "3" | "4" | "5" | "6" | null;
  /** A-1 최근 한 달 자발적으로 읽은 책 권수 */
  voluntary_reading_count?: number | null;
  /** A-4 학년별 척도 7칸(위치=학년, 1학년~중1). null 칸은 해당 없음·아직 오지 않은 학년 */
  life_reading_graph?: ("1" | "2" | "3" | "4" | "5" | null)[] | null;
  /** C-1 */
  interest_topics?: TopicCode[] | null;
  free_text_interest?: string | null;
  /** C-3 */
  preferred_genres?: GenrePreference[] | null;
  /** D-1 자기 인식, 클수록 잘 읽는다고 봄 */
  self_reading_level?: "1" | "2" | "3" | "4" | "5" | null;
  /** A-5 (비독자만) */
  book_image?: BookImage[] | null;
  /** A-6 (비독자만) */
  non_reading_reason?: NonReadingReason[] | null;
}

export interface ProfileResponse {
  id: number;
  user_id: number;
  /** B-1 학년 (7=중1) */
  grade: "4" | "5" | "6" | "7" | null;
  type_1: ReaderType1 | null;
  interest_topics: TopicCode[] | null;
}

/** 전사를 채점에 쓸 수 있는가 — 학생이 잘 읽었는가와 다른 축이다. */
export type QualityGate = "usable" | "retry" | "unusable"

/** 관리자용 문항 — 정답·근거·해설 포함. */
export interface QuestionDetail {
  id: number;
  question_code: string;
  target_area: TargetArea;
  question_text: string;
  choices: string[];
  /** 정답 선지 번호 */
  answer_index: number;
  evidence_text: string;
  explanation: string;
  review_status: ReviewStatus;
}

/** 학생에게 내려보내는 문항 — 정답 번호·근거·해설은 싣지 않는다(부정 방지). */
export interface QuestionPublic {
  id: number;
  target_area: TargetArea;
  question_text: string;
  choices: string[];
}

export interface QuestionResponseResult {
  id: number;
  round_id: number;
  /** 문항이 삭제됐으면 null */
  question_id: number | null;
  /** 고른 선지 번호 */
  student_answer: number;
  is_correct: boolean;
  target_area: TargetArea;
  created_at: string;
}

/** 설문 문항의 상태 (survey_questions.json). */
export type QuestionStatus = "active" | "conditional" | "reserved"

/** 순서를 매긴다. */
export interface RankQuestion {
  code: string;
  block: number | null;
  status: QuestionStatus;
  text: string;
  storage_field: string | null;
  required: boolean;
  show_if: ShowIf | null;
  /** 가정환경 점수(B-3~B-6 합)에 들어가는 문항 */
  env_score: boolean;
  guide_text: string | null;
  usage_note: string[];
  storage_note: string[];
  options_note: string[];
  response_type: "rank";
  options: Option[];
}

/**
 * 지문 1편의 표면 구조 지표 — texts.readability_metrics 에 저장된다.
 *
 * KReaD 지수가 아니다(외부 기관 지수라 산출할 수 없다). 어휘 등급도 어휘의
 * '어려움'이 아니라 어절 길이 분포로 매긴 대리 지표다.
 */
export interface ReadabilityMetrics {
  sentence_count: number;
  /** 어절 수 */
  word_count: number;
  /** 한글 음절 수 */
  syllable_count: number;
  avg_sentence_words: number;
  avg_word_syllables: number;
  /** 긴 어절(5음절 이상) 비율 0~1 */
  long_word_ratio: number;
  clause_density: number;
  /** 서로 다른 어절 / 전체 어절 0~1. 조사를 떼지 않아 과대 추정된다 */
  lexical_variety_ratio: number;
  /** 합성 지표 0~100, 높을수록 어려움. 가중치 잠정 */
  readability_score: number;
  vocabulary_level: VocabularyLevel;
}

export type ReaderType1 = "enthusiast" | "intermittent" | "non_reader"

/** A-2·A-3 만으로 1차 유형을 미리 물어보는 요청. */
export interface ReaderTypeProbe {
  reading_freq?: "1" | "2" | "3" | "4" | "5" | "6" | null;
  reading_attitude?: "1" | "2" | "3" | "4" | "5" | "6" | null;
}

export interface ReaderTypeProbeResponse {
  type_1: ReaderType1;
  /** 조건부 문항(A-5·A-6)을 띄울지. 화면이 분류 규칙을 스스로 해석하지 않게 판단만 내려준다 */
  show_non_reader_questions: boolean;
}

/**
 * 일을 할 수 있는가 — DB 를 실제로 찔러 본다. 실패면 503 과 함께 나간다.
 *
 * 사유 문자열은 싣지 않는다 — 인증 없이 열린 경로라 접속 정보가 새면 안 된다.
 */
export interface Readiness {
  status: HealthStatus;
  checks: ReadinessChecks;
}

export interface ReadinessChecks {
  api: boolean;
  db: boolean;
}

/** 추천 지문 미리보기 한 편 — 리포트를 만든 시점의 제목 사본. */
export interface RecommendedPreview {
  /** texts.id */
  text_id: number;
  title: string;
  /** 지문 장르 */
  genre: TextGenre;
  /** 지문 난도 */
  difficulty: Difficulty;
}

/**
 * 추천 지문의 **참조 목록**, 우선순위 순서.
 *
 * 예전에는 제목·난도·장르까지 복사해 저장했다. 그러면 같은 사실(지문 제목)이
 * texts 와 여기 두 곳에 생긴다(원칙 5). 이제 id 만 남기고, 화면에 보여 줄
 * 때 리포트가 지문 테이블에서 읽는다. 보여 준 그대로의 사본은 리포트에 남는다.
 */
export interface RecommendedTexts {
  /** texts.id. 앞이 우선순위 높음, 중복 없음, 최대 5 */
  text_ids: number[];
}

/** 반려 — 사유 필수. 요청자에게 그대로 보인다. */
export interface RejectRequest {
  resolution_note: string;
}

export type ReliabilityFlag = "normal" | "low" | "unstable"

export interface ReportBrief {
  report_content: ReportContent;
  llm_polished: boolean;
}

/** 학생 리포트 문서. 3층(layer3)은 계약상 무엇이 들어가는지 확인 전이라 두지 않는다. */
export interface ReportContent {
  /** 요약 — 학생이 처음 보는 화면 */
  layer1: ReportSummary;
  /** 더 알아보기 */
  layer2: ReportDetail;
}

/** 2층 — 더 알아보기. */
export interface ReportDetail {
  /** 유창성 */
  fluency: FluencyView;
  /** 독해 */
  comprehension: ComprehensionView;
  /** 메타인지. D-2 미수집이면 null(판정 안 함) */
  metacognition: Metacognition | null;
  /** 처방의 훈련 대상 순서, 최대 2칸 */
  weakness_training: TrainingView[];
}

export interface ReportResponse {
  id: number;
  judgment_id: number;
  report_type: ReportRole;
  report_content: ReportContent;
  disclaimer_flags: Disclaimers;
  llm_polished: boolean;
  review_status: ReviewStatus;
}

export type ReportRole = "student" | "parent" | "teacher"

/** 1층 — 요약. */
export interface ReportSummary {
  label: string;
  /** 라벨 문구의 원래 코드 */
  label_code: Label5;
  strengths: string[];
  encouragement: string;
  /** 처방 추천 순서대로 최대 3편 */
  recommended_preview: RecommendedPreview[];
}

/** 문항 응답 한 건. 문항이 삭제됐으면 문항 칸이 null. */
export interface ResponseDetail {
  target_area: TargetArea;
  /** 고른 선지 번호 */
  student_answer: number;
  is_correct: boolean;
  question_text: string | null;
  /** 정답 선지 번호 */
  answer_index: number | null;
  choices: string[] | null;
}

export type ResumePhase = "reading" | "questions"

/** 이어할 지점. 화면은 phase 에 따라 읽기/문항 화면으로 복귀한다. */
export interface ResumeResponse {
  session_id: number;
  round: RoundResponse;
  round_number: number;
  phase: ResumePhase;
  /** {question_id: 고른 선지 번호} — 복원용 */
  answered: Record<string, number>;
  /** 읽기 시간 미측정이라 지문을 교체했는지 */
  text_reissued: boolean;
}

/** 검수 판정. */
export type ReviewDecision = "advance" | "approve" | "reject"

export interface ReviewItem {
  id: number;
  target_type: ReviewTarget;
  target_id: number;
  target_code: string | null;
  from_status: ReviewStatus;
  to_status: ReviewStatus;
  decision: ReviewDecision;
  reviewer_code: string | null;
  checklist: Checklist | null;
  comment: string | null;
  created_at: string;
}

export interface ReviewRequest {
  target_type: ReviewTarget;
  target_id: number;
  decision: ReviewDecision;
  /** approve 시 7개 모두 true */
  checklist?: ChecklistInput | null;
  comment?: string | null;
}

export interface ReviewResult {
  id: number;
  target_type: ReviewTarget;
  target_id: number;
  target_code: string | null;
  from_status: ReviewStatus;
  to_status: ReviewStatus;
  to_status_label: string;
  decision: ReviewDecision;
}

/** texts/questions/item_sets 공통 3단(실질 5단) 승인 상태. */
export type ReviewStatus = "draft" | "ai_generated" | "auto_checked" | "jun_reviewed" | "approved"

/** 검수 대상의 종류. */
export type ReviewTarget = "text" | "item_set" | "question"

/** 화면에 보내는 회차 집계. */
export interface RoundAggregateView {
  /** 맞힌 문항 수 */
  correct_count: number;
  /** 푼 문항 수 */
  question_count: number;
  /** 정답률 0~1. 문항이 없으면 null */
  accuracy: number | null;
  /** 정답률로 정한 Betts 수준. 문항이 없으면 null */
  betts_level: BettsLevel | null;
  /** A5·A6·A7 순서 */
  areas: AreaTallyView[];
}

export interface RoundCompleteResponse {
  comprehension: RoundAggregateView;
  decision: AdaptiveDecision;
  next_round: RoundResponse | null;
  /** 다음 회차에 줄 지문이 없어 끝냈다 */
  text_shortage: boolean;
  session: SessionResponse;
}

export interface RoundContentResponse {
  round_id: number;
  text_id: number;
  title: string;
  content: string;
  syllable_count: number;
  genre: TextGenre;
  difficulty_level: Difficulty;
  questions: QuestionPublic[];
}

export interface RoundCreate {
  diagnosis_session_id: number;
  round_number: number;
  text_id?: number | null;
  difficulty_level: Difficulty;
  genre: TextGenre;
}

/** 회차 한 개 — 지문·집계·묵독·응답. 미완료 회차는 집계 칸이 null. */
export interface RoundDetail {
  round_number: number;
  difficulty: Difficulty;
  genre: TextGenre;
  text_repeated: boolean;
  text: TextBrief | null;
  betts_level: BettsLevel | null;
  accuracy: number | null;
  correct_count: number | null;
  question_count: number | null;
  reading_time_ms: number | null;
  a4_syllable_per_sec: number | null;
  /** 의미 있는 화면 이탈 횟수 (묵독 원본에서 계산) */
  away_count: number | null;
  /** 이탈 시간 합 (묵독 원본에서 계산) */
  away_total_ms: number | null;
  responses: ResponseDetail[];
}

export interface RoundResponse {
  id: number;
  diagnosis_session_id: number;
  /** 1부터 */
  round_number: number;
  text_id: number | null;
  difficulty_level: Difficulty;
  genre: TextGenre;
  started_at: string;
  completed_at: string | null;
}

export interface RoundsReached {
  /** 미완료 세션이 만든 회차 수 */
  rounds_reached_count: number;
  session_count: number;
}

export interface ScalePoint {
  label: string;
  /** 척도 값. null 은 '해당 없음' */
  value: number | null;
}

export interface SessionBrief {
  id: number;
  status: DiagSessionStatus;
  started_at: string | null;
  completed_at: string | null;
  round_count: number;
  reliability_flag: ReliabilityFlag;
}

export interface SessionCreate {
  profile_id?: number | null;
  silent_mode?: boolean;
  /** 전환기 호환 — 1회차 지문 지정 */
  text_id?: number | null;
}

export interface SessionResponse {
  id: number;
  session_uuid: string | null;
  student_id: number;
  profile_id: number | null;
  text_id: number | null;
  silent_mode: boolean;
  /** 시작한 회차 수 */
  round_count: number;
  status: DiagSessionStatus;
  started_at: string;
  completed_at: string | null;
}

/** 조건부 문항이 뜨는 조건. */
export interface ShowIf {
  type_1: ReaderType1;
}

/**
 * 묵독 한 번의 측정 결과.
 *
 * 읽기 시간은 **'읽기 시작'과 '다 읽었어' 버튼 사이의 실제 시각 차이(ms)**다.
 * 예전에는 1초마다 1씩 오르는 화면 타이머를 보냈다. 1초 단위라 거칠고,
 * 탭이 가려지면 브라우저가 타이머를 늦춰 시간이 짧게 잡혔다(→ A4 부풀림).
 */
export interface SilentReadingSubmit {
  /** diagnosis_sessions.id */
  session_id: number;
  /** diagnosis_rounds.id — 어느 지문을 읽었나 */
  round_id: number;
  /** 두 버튼 사이의 실제 시각 차이(ms) */
  reading_time_ms: number;
  /** 읽는 동안의 이탈 이벤트, 시간순 */
  away_events: AwayEvent[];
}

/** 발화 구간 요약. detected 가 아니면 시간 칸은 전부 null 이다. */
export interface SpeechTiming {
  vad_status: VadStatus;
  speech_start_ms: number | null;
  speech_end_ms: number | null;
  /** 첫 발화 시작~마지막 발화 끝. 도메인 절차의 소요시간 */
  speech_span_ms: number | null;
  /** 실제 소리 낸 시간의 합 — 휴지 제외 */
  voiced_ms: number | null;
  audio_duration_ms: number | null;
  segment_count: number | null;
  pause_count: number | null;
  pause_total_ms: number | null;
  longest_pause_ms: number | null;
}

export interface Stats {
  /** Label5 정의 순서, 5칸 전부 */
  label_distribution: LabelCount[];
  /** 장르 × 난도 6칸 전부 (빈 칸은 0) */
  text_distribution: TextCell[];
  judgment_count: number;
  /** 판정 전체의 평균 정답률. 판정이 없으면 null */
  mean_accuracy: number | null;
}

export interface StatusCount {
  status: DiagSessionStatus;
  session_count: number;
}

export interface StatusLabel {
  code: ReviewStatus;
  label: string;
}

export type SttAdapterName = "mock" | "clova"

/** STT 연결 상태 — 관리자 시스템 점검용. */
export interface SttHealth {
  stt_available: boolean;
  adapter: SttAdapterName;
}

export interface StudentBrief {
  id: number;
  name: string;
  username: string;
}

/** 화면에 내려주는 설문 — 화면에 뜨는 문항만(active·conditional). */
export interface SurveyQuestions {
  questions: (ChoiceQuestion | MultiQuestion | RankQuestion | NumberQuestion | GradeHistoryQuestion | HybridQuestion)[];
}

export interface SystemStatus {
  app: AppInfo;
  database: DatabaseInfo;
  deployment: DeploymentInfo;
  legal: LegalInfoView;
}

export type TargetArea = "A5" | "A6" | "A7"

export interface TextBrief {
  id: number;
  title: string;
  text_code: string;
  syllable_count: number;
}

/** 승인 지문의 장르 × 난도 한 칸. */
export interface TextCell {
  genre: TextGenre;
  difficulty: Difficulty;
  text_count: number;
}

/** 지문 본문 + 문항 전체. 목록 칸에 본문·근거·문항을 더했다. */
export interface TextDetail {
  id: number;
  text_code: string;
  title: string;
  grade_group: GradeGroup;
  genre: TextGenre;
  difficulty: Difficulty;
  syllable_count: number;
  topic_tags: string[];
  review_status: ReviewStatus;
  created_by_role: ContentAuthor | null;
  question_count: number;
  /** 표면 구조 합성 지표 0~100 (STR-103). 미산출이면 null */
  readability_score: number | null;
  sentence_complexity: number | null;
  vocabulary_level: VocabularyLevel | null;
  content: string;
  text_structure: TextStructure | null;
  readability_metrics: ReadabilityMetrics | null;
  /** 외부 기관 지수. 산출할 수 없어 항상 null */
  kread_index: number | null;
  questions: QuestionDetail[];
}

export type TextGenre = "narrative" | "expository"

export type TextStructure = "chronological" | "compare_contrast" | "cause_effect" | "problem_solution"

/** 지문 풀 목록 한 줄. */
export interface TextSummary {
  id: number;
  text_code: string;
  title: string;
  grade_group: GradeGroup;
  genre: TextGenre;
  difficulty: Difficulty;
  syllable_count: number;
  topic_tags: string[];
  review_status: ReviewStatus;
  created_by_role: ContentAuthor | null;
  question_count: number;
  /** 표면 구조 합성 지표 0~100 (STR-103). 미산출이면 null */
  readability_score: number | null;
  sentence_complexity: number | null;
  vocabulary_level: VocabularyLevel | null;
}

export interface TokenResponse {
  access_token: string;
  token_type: "bearer";
  user: UserResponse;
}

export type ToneCode = "challenge" | "encourage" | "autonomy" | "scaffold" | "success_first"

/** 관심 주제 코드 — 단일 진실 공급원: survey_questions.json student C-1 선지 */
export type TopicCode = "animal" | "science" | "history" | "sports" | "mystery" | "fantasy" | "humor" | "friendship" | "family" | "art_music" | "cooking" | "game" | "world" | "horror" | "society" | "other"

/**
 * 약점 훈련 대상, 우선순위 순서, 최대 2칸.
 *
 * 예전에는 정답률과 활동 안내 문장까지 담았다. 정답률은 판정의 약점
 * 프로필에 이미 있고(원칙 5), 안내 문장은 영역에서 정해지는 표시용
 * 문구다. 이제 대상만 남긴다. 대상이 없으면 훈련이 필요 없다는 뜻이다.
 */
export interface TrainingPlan {
  /** 우선순위 순, 최대 2칸, 중복 없음. 비면 훈련 불필요 */
  targets: TrainingTarget[];
}

/** 약점 훈련 대상 한 칸. */
export interface TrainingTarget {
  /** 훈련할 독해 영역 */
  area: TargetArea;
  /** 훈련할 지문 장르 */
  genre: TextGenre;
}

/** 약점 훈련 안내 한 칸 — 처방의 훈련 대상에 안내 문장을 붙였다. */
export interface TrainingView {
  /** 훈련할 독해 영역 */
  area: TargetArea;
  /** 훈련할 지문 장르 */
  genre: TextGenre;
  activity: string;
}

/** 역할별 계정 수 (관리자 제외). */
export interface UserCounts {
  student_count: number;
  parent_count: number;
  teacher_count: number;
  total_count: number;
}

export interface UserLogin {
  username: string;
  password: string;
}

export interface UserNameUpdate {
  name: string;
}

export interface UserRegister {
  username: string;
  password: string;
  name: string;
  role?: UserRole;
  grade?: GradeLevel | null;
}

export interface UserResponse {
  id: number;
  username: string;
  name: string;
  role: UserRole;
  grade: GradeLevel | null;
  is_active: boolean;
  must_change_password: boolean;
}

export type UserRole = "student" | "parent" | "teacher" | "admin"

export type VadStatus = "unavailable" | "no_speech" | "detected"

export interface ValidationError {
  loc: (string | number)[];
  msg: string;
  type: string;
}

/** 지문 어휘 등급 — 어절 길이 기반 대리 지표 (content.readability). */
export type VocabularyLevel = "basic" | "intermediate" | "advanced"

/** 화면에 보내는 약점 칸 — 저장 스키마에 서버가 계산한 정답률을 붙였다. */
export interface WeaknessCellView {
  /** 독해 영역 */
  area: TargetArea;
  /** 지문 장르 */
  genre: TextGenre;
  /** 맞힌 문항 수 */
  correct_count: number;
  /** 푼 문항 수 */
  question_count: number;
  /** 정답률 0~1. 문항이 없던 칸은 null */
  accuracy: number | null;
}

/** 화면에 보내는 약점 프로필 (판정 API · 관리자 진단 상세). */
export interface WeaknessProfileView {
  /** 6칸, 저장 스키마와 같은 순서 */
  cells: WeaknessCellView[];
}

/** API 경로별 응답 타입. 키는 `메서드 경로` 다. 스키마가 없는 API 는 싣지 않는다. */
export interface ApiResponses {
  "GET /api/account/deletion-request": MyDeletionRequests;
  "POST /api/account/deletion-request": DeletionRequestReceipt;
  "GET /api/account/deletion-request/reasons": DeletionReasons;
  "POST /api/account/deletion-request/{request_id}/cancel": DeletionRequestView;
  "GET /api/admin/books": BooksCatalog;
  "GET /api/admin/consents": ConsentListResponse;
  "POST /api/admin/consents": ConsentRow;
  "POST /api/admin/consents/{user_id}/revoke": ConsentRow;
  "GET /api/admin/diagnoses": DiagnosisListItem[];
  "GET /api/admin/diagnoses/{session_id}": DiagnosisDetail;
  "GET /api/admin/disposals": DisposalLogItem[];
  "POST /api/admin/disposals": DisposalResult;
  "GET /api/admin/disposals/preview/{user_id}": DisposalPreview;
  "GET /api/admin/disposals/reasons": CodeLabel[];
  "GET /api/admin/disposals/requests": DeletionRequestList;
  "POST /api/admin/disposals/requests/{request_id}/reject": DeletionRequestView;
  "GET /api/admin/overview": Overview;
  "GET /api/admin/pilot/difficulty-validity": DifficultyValidity;
  "GET /api/admin/pilot/distributions": Distributions;
  "GET /api/admin/pilot/dropoff": Dropoff;
  "GET /api/admin/pilot/duration": Duration;
  "GET /api/admin/pilot/outliers": Outliers;
  "GET /api/admin/reviews": ReviewItem[];
  "POST /api/admin/reviews": ReviewResult;
  "GET /api/admin/reviews/checklist": ChecklistInfo;
  "GET /api/admin/stats": Stats;
  "GET /api/admin/system": SystemStatus;
  "GET /api/admin/texts": TextSummary[];
  "GET /api/admin/texts/{text_id}": TextDetail;
  "GET /api/admin/users": UserResponse[];
  "GET /api/admin/users/count": UserCounts;
  "GET /api/audio/health": SttHealth;
  "POST /api/audio/oral": OralTranscription;
  "POST /api/audio/timing": SpeechTiming;
  "POST /api/auth/admin/users": IssuedCredential;
  "POST /api/auth/admin/users/bulk": BulkIssued;
  "PATCH /api/auth/admin/users/{user_id}/active": UserResponse;
  "POST /api/auth/admin/users/{user_id}/reset-password": IssuedCredential;
  "POST /api/auth/change-credentials": TokenResponse;
  "POST /api/auth/login": TokenResponse;
  "GET /api/auth/me": UserResponse;
  "POST /api/auth/register": UserResponse;
  "PATCH /api/auth/users/{user_id}/name": UserResponse;
  "POST /api/diagnosis/comprehension": QuestionResponseResult;
  "POST /api/diagnosis/fluency/oral": FluencyResultResponse;
  "POST /api/diagnosis/fluency/silent": FluencyResultResponse;
  "GET /api/diagnosis/my/books": BooksForMe;
  "GET /api/diagnosis/my/sessions": MySessionItem[];
  "GET /api/diagnosis/my/summary": MySummaryResponse;
  "POST /api/diagnosis/profile": ProfileResponse;
  "POST /api/diagnosis/reader-type": ReaderTypeProbeResponse;
  "GET /api/diagnosis/result/{session_id}": DiagnosisResultResponse;
  "POST /api/diagnosis/round": RoundResponse;
  "POST /api/diagnosis/round/{round_id}/complete": RoundCompleteResponse;
  "GET /api/diagnosis/round/{round_id}/content": RoundContentResponse;
  "POST /api/diagnosis/session": SessionResponse;
  "POST /api/diagnosis/session/{session_id}/abandon": SessionResponse;
  "PATCH /api/diagnosis/session/{session_id}/complete": SessionResponse;
  "POST /api/diagnosis/session/{session_id}/finalize": FinalizeResponse;
  "GET /api/diagnosis/session/{session_id}/judgment": FinalizeResponse;
  "GET /api/diagnosis/session/{session_id}/report": ReportResponse;
  "POST /api/diagnosis/session/{session_id}/report": ReportResponse;
  "POST /api/diagnosis/session/{session_id}/resume": ResumeResponse;
  "POST /api/diagnosis/session/{session_id}/start": RoundResponse;
  "GET /api/diagnosis/survey/definition": SurveyQuestions;
  "GET /api/health": Health;
  "GET /api/health/ready": Readiness;
  "POST /api/parent/survey": ParentSurveyOut;
  "GET /api/parent/survey/definition": SurveyQuestions;
  "GET /api/parent/survey/latest": ParentSurveyOut | null;
  "GET /api/parent/survey/{profile_id}": ParentSurveyOut;
}
