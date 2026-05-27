import 'utils.dart';

enum RunState { idle, running, completed, failed }

const safeMinDelaySeconds = 0.5;
const defaultDelaySeconds = 0.5;
const maxDelaySeconds = 2.0;

double clampDelaySeconds(num? value) {
  final raw = value?.toDouble() ?? defaultDelaySeconds;
  if (!raw.isFinite) {
    return defaultDelaySeconds;
  }
  if (raw < safeMinDelaySeconds) {
    return safeMinDelaySeconds;
  }
  if (raw > maxDelaySeconds) {
    return maxDelaySeconds;
  }
  return raw;
}

class CustomApiSource {
  const CustomApiSource({
    required this.id,
    required this.name,
    required this.apiKey,
    required this.envVar,
    this.enabled = true,
    this.searchEnabled = true,
    this.endpoint = '',
    this.method = 'GET',
    this.authType = 'none',
    this.apiKeyParam = 'api_key',
    this.apiKeyHeader = 'Authorization',
    this.queryParams = '{"q":"{title}"}',
    this.headers = '{}',
    this.restProfileJson = '',
    this.resultsPath = 'results',
    this.titlePath = 'title',
    this.authorsPath = 'authors',
    this.yearPath = 'year',
    this.doiPath = 'doi',
    this.urlPath = 'url',
    this.venuePath = 'venue',
    this.typePath = 'type',
  });

  final String id;
  final String name;
  final String apiKey;
  final String envVar;
  final bool enabled;
  final bool searchEnabled;
  final String endpoint;
  final String method;
  final String authType;
  final String apiKeyParam;
  final String apiKeyHeader;
  final String queryParams;
  final String headers;
  final String restProfileJson;
  final String resultsPath;
  final String titlePath;
  final String authorsPath;
  final String yearPath;
  final String doiPath;
  final String urlPath;
  final String venuePath;
  final String typePath;

  bool get hasCustomRestProfile =>
      endpoint.trim().isNotEmpty || restProfileJson.trim().isNotEmpty;

  Map<String, dynamic> toJson() => {
        'id': id,
        'name': name,
        'apiKey': apiKey,
        'envVar': envVar,
        'enabled': enabled,
        'searchEnabled': searchEnabled,
        'endpoint': endpoint,
        'method': method,
        'authType': authType,
        'apiKeyParam': apiKeyParam,
        'apiKeyHeader': apiKeyHeader,
        'queryParams': queryParams,
        'headers': headers,
        'restProfileJson': restProfileJson,
        'resultsPath': resultsPath,
        'titlePath': titlePath,
        'authorsPath': authorsPath,
        'yearPath': yearPath,
        'doiPath': doiPath,
        'urlPath': urlPath,
        'venuePath': venuePath,
        'typePath': typePath,
      };

  factory CustomApiSource.fromJson(Map<String, dynamic> json) {
    return CustomApiSource(
      id: asString(json['id']),
      name: asString(json['name']),
      apiKey: asString(json['apiKey']),
      envVar: asString(json['envVar']),
      enabled: json['enabled'] as bool? ?? true,
      searchEnabled: json['searchEnabled'] as bool? ?? true,
      endpoint: asString(json['endpoint']),
      method:
          asString(json['method']).isEmpty ? 'GET' : asString(json['method']),
      authType: asString(json['authType']).isEmpty
          ? 'none'
          : asString(json['authType']),
      apiKeyParam: asString(json['apiKeyParam']).isEmpty
          ? 'api_key'
          : asString(json['apiKeyParam']),
      apiKeyHeader: asString(json['apiKeyHeader']).isEmpty
          ? 'Authorization'
          : asString(json['apiKeyHeader']),
      queryParams: asString(json['queryParams']).isEmpty
          ? '{"q":"{title}"}'
          : asString(json['queryParams']),
      headers:
          asString(json['headers']).isEmpty ? '{}' : asString(json['headers']),
      restProfileJson: asString(json['restProfileJson']),
      resultsPath: asString(json['resultsPath']).isEmpty
          ? 'results'
          : asString(json['resultsPath']),
      titlePath: asString(json['titlePath']).isEmpty
          ? 'title'
          : asString(json['titlePath']),
      authorsPath: asString(json['authorsPath']).isEmpty
          ? 'authors'
          : asString(json['authorsPath']),
      yearPath: asString(json['yearPath']).isEmpty
          ? 'year'
          : asString(json['yearPath']),
      doiPath:
          asString(json['doiPath']).isEmpty ? 'doi' : asString(json['doiPath']),
      urlPath:
          asString(json['urlPath']).isEmpty ? 'url' : asString(json['urlPath']),
      venuePath: asString(json['venuePath']).isEmpty
          ? 'venue'
          : asString(json['venuePath']),
      typePath: asString(json['typePath']).isEmpty
          ? 'type'
          : asString(json['typePath']),
    );
  }

  CustomApiSource copyWith({
    String? id,
    String? name,
    String? apiKey,
    String? envVar,
    bool? enabled,
    bool? searchEnabled,
    String? endpoint,
    String? method,
    String? authType,
    String? apiKeyParam,
    String? apiKeyHeader,
    String? queryParams,
    String? headers,
    String? restProfileJson,
    String? resultsPath,
    String? titlePath,
    String? authorsPath,
    String? yearPath,
    String? doiPath,
    String? urlPath,
    String? venuePath,
    String? typePath,
  }) {
    return CustomApiSource(
      id: id ?? this.id,
      name: name ?? this.name,
      apiKey: apiKey ?? this.apiKey,
      envVar: envVar ?? this.envVar,
      enabled: enabled ?? this.enabled,
      searchEnabled: searchEnabled ?? this.searchEnabled,
      endpoint: endpoint ?? this.endpoint,
      method: method ?? this.method,
      authType: authType ?? this.authType,
      apiKeyParam: apiKeyParam ?? this.apiKeyParam,
      apiKeyHeader: apiKeyHeader ?? this.apiKeyHeader,
      queryParams: queryParams ?? this.queryParams,
      headers: headers ?? this.headers,
      restProfileJson: restProfileJson ?? this.restProfileJson,
      resultsPath: resultsPath ?? this.resultsPath,
      titlePath: titlePath ?? this.titlePath,
      authorsPath: authorsPath ?? this.authorsPath,
      yearPath: yearPath ?? this.yearPath,
      doiPath: doiPath ?? this.doiPath,
      urlPath: urlPath ?? this.urlPath,
      venuePath: venuePath ?? this.venuePath,
      typePath: typePath ?? this.typePath,
    );
  }
}

class LlmApiConfig {
  const LlmApiConfig({
    required this.id,
    required this.name,
    required this.provider,
    required this.model,
    required this.baseUrl,
    required this.apiKey,
    this.enabled = false,
  });

  final String id;
  final String name;
  final String provider;
  final String model;
  final String baseUrl;
  final String apiKey;
  final bool enabled;

  Map<String, dynamic> toJson() => {
        'id': id,
        'name': name,
        'provider': provider,
        'model': model,
        'baseUrl': baseUrl,
        'apiKey': apiKey,
        'enabled': enabled,
      };

  factory LlmApiConfig.fromJson(Map<String, dynamic> json) {
    return LlmApiConfig(
      id: asString(json['id']),
      name: asString(json['name']).isEmpty
          ? '默认 LLM'
          : asString(json['name']),
      provider: asString(json['provider']).isEmpty
          ? 'openai-compatible'
          : asString(json['provider']),
      model: asString(json['model']).isEmpty
          ? 'gpt-4o-mini'
          : asString(json['model']),
      baseUrl: asString(json['baseUrl']).isEmpty
          ? 'https://api.openai.com/v1'
          : asString(json['baseUrl']),
      apiKey: asString(json['apiKey']),
      enabled: json['enabled'] as bool? ?? false,
    );
  }

  LlmApiConfig copyWith({
    String? id,
    String? name,
    String? provider,
    String? model,
    String? baseUrl,
    String? apiKey,
    bool? enabled,
  }) {
    return LlmApiConfig(
      id: id ?? this.id,
      name: name ?? this.name,
      provider: provider ?? this.provider,
      model: model ?? this.model,
      baseUrl: baseUrl ?? this.baseUrl,
      apiKey: apiKey ?? this.apiKey,
      enabled: enabled ?? this.enabled,
    );
  }
}

const sourceDefaults = [
  ('crossref', 'CrossRef', true),
  ('openalex', 'OpenAlex', false),
  ('semantic-scholar', 'Semantic Scholar', false),
  ('arxiv', 'arXiv', false),
  ('pubmed', 'PubMed', false),
  ('dblp', 'DBLP', false),
  ('url', 'URL 验证', false),
  ('springer', 'Springer Nature', false),
  ('ieee', 'IEEE Xplore', false),
  ('core', 'CORE', false),
];

List<String> defaultSourceOrder() => sourceDefaults.map((s) => s.$1).toList();

class RunSettings {
  const RunSettings({
    required this.threshold,
    required this.delay,
    required this.email,
    required this.sources,
    required this.sourceOrder,
    required this.searchMode,
    required this.doiCheck,
    required this.llmParseMode,
    required this.llmProvider,
    required this.llmModel,
    required this.llmBaseUrl,
    required this.llmApiKey,
    this.llmApiConfigs = const <LlmApiConfig>[],
    this.selectedLlmApiConfigId = '',
    required this.customApiSources,
    required this.useCrossref,
    required this.useOpenAlex,
    required this.useSemanticScholar,
    required this.useArxiv,
    required this.usePubMed,
    required this.useDblp,
    required this.useUrlVerify,
    required this.useSpringer,
    required this.useIeee,
    required this.useCore,
  });

  final double threshold;
  final double delay;
  final String email;
  final String sources;
  final List<String> sourceOrder;
  final String searchMode;
  final String doiCheck;
  final String llmParseMode;
  final String llmProvider;
  final String llmModel;
  final String llmBaseUrl;
  final String llmApiKey;
  final List<LlmApiConfig> llmApiConfigs;
  final String selectedLlmApiConfigId;
  final List<CustomApiSource> customApiSources;
  final bool useCrossref;
  final bool useOpenAlex;
  final bool useSemanticScholar;
  final bool useArxiv;
  final bool usePubMed;
  final bool useDblp;
  final bool useUrlVerify;
  final bool useSpringer;
  final bool useIeee;
  final bool useCore;

  bool isSourceEnabled(String key) {
    if (key.startsWith('custom:')) {
      final id = key.substring('custom:'.length);
      for (final source in customApiSources) {
        if (source.id == id) {
          return source.enabled &&
              source.searchEnabled &&
              source.hasCustomRestProfile;
        }
      }
      return false;
    }
    return switch (key) {
      'crossref' => useCrossref,
      'openalex' => useOpenAlex,
      'semantic-scholar' => useSemanticScholar,
      'arxiv' => useArxiv,
      'pubmed' => usePubMed,
      'dblp' => useDblp,
      'url' => useUrlVerify,
      'springer' => useSpringer,
      'ieee' => useIeee,
      'core' => useCore,
      _ => true,
    };
  }

  String get effectiveSources => sourceOrder.where(isSourceEnabled).join(',');

  Map<String, dynamic> toJson() => {
        'threshold': threshold,
        'delay': clampDelaySeconds(delay),
        'email': email,
        'sources': effectiveSources,
        'sourceOrder': sourceOrder,
        'searchMode': searchMode,
        'doiCheck': doiCheck,
        'llmParseMode': llmParseMode,
        'llmProvider': llmProvider,
        'llmModel': llmModel,
        'llmBaseUrl': llmBaseUrl,
        'llmApiKey': llmApiKey,
        'llmApiConfigs': llmApiConfigs.map((s) => s.toJson()).toList(),
        'selectedLlmApiConfigId': selectedLlmApiConfigId,
        'customApiSources': customApiSources.map((s) => s.toJson()).toList(),
        'useCrossref': useCrossref,
        'useOpenAlex': useOpenAlex,
        'useSemanticScholar': useSemanticScholar,
        'useArxiv': useArxiv,
        'usePubMed': usePubMed,
        'useDblp': useDblp,
        'useUrlVerify': useUrlVerify,
        'useSpringer': useSpringer,
        'useIeee': useIeee,
        'useCore': useCore,
      };

  factory RunSettings.fromJson(Map<String, dynamic> json) {
    final apiSources = (json['customApiSources'] as List<dynamic>?)
            ?.map((e) => CustomApiSource.fromJson(e as Map<String, dynamic>))
            .toList() ??
        const <CustomApiSource>[];
    final llmConfigs = (json['llmApiConfigs'] as List<dynamic>?)
            ?.whereType<Map>()
            .map((e) => LlmApiConfig.fromJson(Map<String, dynamic>.from(e)))
            .toList() ??
        const <LlmApiConfig>[];
    final orderRaw = json['sourceOrder'];
    final order = (orderRaw is List)
        ? orderRaw.map((e) => e.toString()).toList()
        : defaultSourceOrder();
    return RunSettings(
      threshold: (json['threshold'] as num?)?.toDouble() ?? 0.85,
      delay: clampDelaySeconds(json['delay'] as num?),
      email: asString(json['email']),
      sources: asString(json['sources']),
      sourceOrder: order,
      searchMode: asString(json['searchMode']).isEmpty
          ? 'strict'
          : asString(json['searchMode']),
      doiCheck:
          asString(json['doiCheck']).isEmpty ? 'auto' : asString(json['doiCheck']),
      llmParseMode: asString(json['llmParseMode']).isEmpty
          ? 'off'
          : asString(json['llmParseMode']),
      llmProvider: asString(json['llmProvider']).isEmpty
          ? 'openai-compatible'
          : asString(json['llmProvider']),
      llmModel: asString(json['llmModel']).isEmpty
          ? 'gpt-4o-mini'
          : asString(json['llmModel']),
      llmBaseUrl: asString(json['llmBaseUrl']).isEmpty
          ? 'https://api.openai.com/v1'
          : asString(json['llmBaseUrl']),
      llmApiKey: asString(json['llmApiKey']),
      llmApiConfigs: llmConfigs,
      selectedLlmApiConfigId: asString(json['selectedLlmApiConfigId']),
      customApiSources: apiSources,
      useCrossref: json['useCrossref'] as bool? ?? true,
      useOpenAlex: json['useOpenAlex'] as bool? ?? true,
      useSemanticScholar: json['useSemanticScholar'] as bool? ?? true,
      useArxiv: json['useArxiv'] as bool? ?? true,
      usePubMed: json['usePubMed'] as bool? ?? true,
      useDblp: json['useDblp'] as bool? ?? true,
      useUrlVerify: json['useUrlVerify'] as bool? ?? true,
      useSpringer: json['useSpringer'] as bool? ?? true,
      useIeee: json['useIeee'] as bool? ?? true,
      useCore: json['useCore'] as bool? ?? true,
    );
  }
}

class RunSummary {
  const RunSummary({
    this.total = 0,
    this.found = 0,
    this.notFound = 0,
    this.needsReview = 0,
    this.skipped = 0,
    this.highRisk = 0,
    this.mediumRisk = 0,
    this.lowRisk = 0,
    this.authorMismatch = 0,
    this.yearMismatch = 0,
    this.doiMismatch = 0,
    this.markdownPath = '',
    this.csvPath = '',
    this.outputDir = '',
    this.citationConsistencyPath = '',
    this.reportSummary = '',
    this.missingReferenceCitations = 0,
    this.uncitedReferences = 0,
    this.duplicateReferenceSignatures = 0,
  });

  final int total;
  final int found;
  final int notFound;
  final int needsReview;
  final int skipped;
  final int highRisk;
  final int mediumRisk;
  final int lowRisk;
  final int authorMismatch;
  final int yearMismatch;
  final int doiMismatch;
  final String markdownPath;
  final String csvPath;
  final String outputDir;
  final String citationConsistencyPath;
  final String reportSummary;
  final int missingReferenceCitations;
  final int uncitedReferences;
  final int duplicateReferenceSignatures;

  RunSummary copyWith({
    int? total,
    int? found,
    int? notFound,
    int? needsReview,
    int? skipped,
    int? highRisk,
    int? mediumRisk,
    int? lowRisk,
    int? authorMismatch,
    int? yearMismatch,
    int? doiMismatch,
    String? markdownPath,
    String? csvPath,
    String? outputDir,
    String? citationConsistencyPath,
    String? reportSummary,
    int? missingReferenceCitations,
    int? uncitedReferences,
    int? duplicateReferenceSignatures,
  }) {
    return RunSummary(
      total: total ?? this.total,
      found: found ?? this.found,
      notFound: notFound ?? this.notFound,
      needsReview: needsReview ?? this.needsReview,
      skipped: skipped ?? this.skipped,
      highRisk: highRisk ?? this.highRisk,
      mediumRisk: mediumRisk ?? this.mediumRisk,
      lowRisk: lowRisk ?? this.lowRisk,
      authorMismatch: authorMismatch ?? this.authorMismatch,
      yearMismatch: yearMismatch ?? this.yearMismatch,
      doiMismatch: doiMismatch ?? this.doiMismatch,
      markdownPath: markdownPath ?? this.markdownPath,
      csvPath: csvPath ?? this.csvPath,
      outputDir: outputDir ?? this.outputDir,
      citationConsistencyPath:
          citationConsistencyPath ?? this.citationConsistencyPath,
      reportSummary: reportSummary ?? this.reportSummary,
      missingReferenceCitations:
          missingReferenceCitations ?? this.missingReferenceCitations,
      uncitedReferences: uncitedReferences ?? this.uncitedReferences,
      duplicateReferenceSignatures:
          duplicateReferenceSignatures ?? this.duplicateReferenceSignatures,
    );
  }

  factory RunSummary.fromJson(Map<String, dynamic> json) {
    return RunSummary(
      total: asInt(json['total']),
      found: asInt(json['found']),
      notFound: asInt(json['not_found']),
      needsReview: asInt(json['needs_review']),
      skipped: asInt(json['skipped']),
      highRisk: asInt(json['high_risk']),
      mediumRisk: asInt(json['medium_risk']),
      lowRisk: asInt(json['low_risk']),
      authorMismatch: asInt(json['author_mismatch']),
      yearMismatch: asInt(json['year_mismatch']),
      doiMismatch: asInt(json['doi_mismatch']),
      markdownPath: asString(json['markdown_path']),
      csvPath: asString(json['csv_path']),
      outputDir: asString(json['output_dir']),
      citationConsistencyPath: asString(json['citation_consistency_path']),
      reportSummary: asString(json['report_summary']),
      missingReferenceCitations: asInt(json['missing_reference_citations']),
      uncitedReferences: asInt(json['uncited_references']),
      duplicateReferenceSignatures:
          asInt(json['duplicate_reference_signatures']),
    );
  }
}

class EntryResult {
  const EntryResult({
    required this.key,
    required this.title,
    required this.status,
    required this.needsReview,
    required this.riskLevel,
    required this.confidenceScore,
    required this.suggestedAction,
    required this.source,
    required this.similarity,
    required this.reason,
    required this.matchedTitle,
    required this.riskExplanation,
    required this.fixSuggestion,
    required this.fixSuggestionBasis,
    required this.parser,
    required this.parserNote,
    required this.parserConfidence,
    required this.parserWarning,
    required this.llmParseMode,
    required this.candidateCount,
    required this.arbitrationReason,
    required this.sourceTrace,
    required this.searchMode,
    required this.sourceOrder,
    required this.actualQueryTrace,
    required this.adoptedSource,
    required this.doiCheckStatus,
    required this.doiCheckMessage,
    required this.doiResolvedUrl,
    required this.doiTargetTitle,
    required this.doiTargetYear,
    required this.doiTargetDoi,
    required this.alternativeCandidates,
    required this.candidateConflict,
    required this.standardCitationAvailable,
    required this.standardCitationBasis,
    required this.standardCitationApa,
    required this.standardCitationBibtex,
    required this.standardCitationGbt7714,
    required this.authorCheck,
    required this.authorReason,
    required this.yearCheck,
    required this.yearReason,
    required this.doiCheck,
    required this.doiReason,
    required this.bibDoi,
    required this.matchedDoi,
    required this.bibUrl,
    required this.matchedUrl,
    required this.bibYear,
    required this.matchedYear,
    required this.bibAuthors,
    required this.matchedAuthors,
    required this.missingAuthors,
    required this.extraAuthors,
    required this.bibAuthorCount,
    required this.matchedAuthorCount,
    required this.matchedVenue,
    required this.matchedType,
    this.webEvidence = false,
    this.evidenceKind = '',
    this.webEvidenceNote = '',
    this.webEvidenceLinks = '',
    this.webEvidenceResults = '',
    this.snippet = '',
  });

  final String key;
  final String title;
  final String status;
  final bool needsReview;
  final String riskLevel;
  final int confidenceScore;
  final String suggestedAction;
  final String source;
  final double? similarity;
  final String reason;
  final String matchedTitle;
  final String riskExplanation;
  final String fixSuggestion;
  final String fixSuggestionBasis;
  final String parser;
  final String parserNote;
  final String parserConfidence;
  final String parserWarning;
  final String llmParseMode;
  final int candidateCount;
  final String arbitrationReason;
  final String sourceTrace;
  final String searchMode;
  final String sourceOrder;
  final String actualQueryTrace;
  final String adoptedSource;
  final String doiCheckStatus;
  final String doiCheckMessage;
  final String doiResolvedUrl;
  final String doiTargetTitle;
  final String doiTargetYear;
  final String doiTargetDoi;
  final String alternativeCandidates;
  final String candidateConflict;
  final bool standardCitationAvailable;
  final String standardCitationBasis;
  final String standardCitationApa;
  final String standardCitationBibtex;
  final String standardCitationGbt7714;
  final String authorCheck;
  final String authorReason;
  final String yearCheck;
  final String yearReason;
  final String doiCheck;
  final String doiReason;
  final String bibDoi;
  final String matchedDoi;
  final String bibUrl;
  final String matchedUrl;
  final String bibYear;
  final String matchedYear;
  final String bibAuthors;
  final String matchedAuthors;
  final String missingAuthors;
  final String extraAuthors;
  final int bibAuthorCount;
  final int matchedAuthorCount;
  final String matchedVenue;
  final String matchedType;
  final bool webEvidence;
  final String evidenceKind;
  final String webEvidenceNote;
  final String webEvidenceLinks;
  final String webEvidenceResults;
  final String snippet;

  factory EntryResult.fromJson(Map<String, dynamic> json) {
    final result = json['result'] is Map<String, dynamic>
        ? json['result'] as Map<String, dynamic>
        : const <String, dynamic>{};
    return EntryResult(
      key: asString(result['key']),
      title: asString(result['title']),
      status: asString(result['status']),
      needsReview: asString(result['needs_review']) == 'Yes',
      riskLevel: asString(result['risk_level']),
      confidenceScore: asInt(result['confidence_score']),
      suggestedAction: asString(result['suggested_action']),
      source: asString(result['source']),
      similarity: asDouble(result['similarity']),
      reason: asString(result['reason']),
      matchedTitle: asString(result['matched_title']),
      riskExplanation: asString(result['risk_explanation']),
      fixSuggestion: asString(result['fix_suggestion']),
      fixSuggestionBasis: asString(result['fix_suggestion_basis']),
      parser: asString(result['parser']),
      parserNote: asString(result['parser_note']),
      parserConfidence: asString(result['parser_confidence']),
      parserWarning: asString(result['parser_warning']),
      llmParseMode: asString(result['llm_parse_mode']),
      candidateCount: asInt(result['candidate_count']),
      arbitrationReason: asString(result['arbitration_reason']),
      sourceTrace: asString(result['source_trace']),
      searchMode: asString(result['search_mode']),
      sourceOrder: asString(result['source_order']),
      actualQueryTrace: asString(result['actual_query_trace']),
      adoptedSource: asString(result['adopted_source']),
      doiCheckStatus: asString(result['doi_check_status']),
      doiCheckMessage: asString(result['doi_check_message']),
      doiResolvedUrl: asString(result['doi_resolved_url']),
      doiTargetTitle: asString(result['doi_target_title']),
      doiTargetYear: asString(result['doi_target_year']),
      doiTargetDoi: asString(result['doi_target_doi']),
      alternativeCandidates: asString(result['alternative_candidates']),
      candidateConflict: asString(result['candidate_conflict']),
      standardCitationAvailable:
          asString(result['standard_citation_available']) == 'Yes',
      standardCitationBasis: asString(result['standard_citation_basis']),
      standardCitationApa: asString(result['standard_citation_apa']),
      standardCitationBibtex: asString(result['standard_citation_bibtex']),
      standardCitationGbt7714: asString(result['standard_citation_gbt7714']),
      authorCheck: asString(result['author_check']),
      authorReason: asString(result['author_reason']),
      yearCheck: asString(result['year_check']),
      yearReason: asString(result['year_reason']),
      doiCheck: asString(result['doi_check']),
      doiReason: asString(result['doi_reason']),
      bibDoi: asString(result['bib_doi']),
      matchedDoi: asString(result['matched_doi']),
      bibUrl: asString(result['bib_url']).isEmpty
          ? asString(result['input_url'])
          : asString(result['bib_url']),
      matchedUrl: asString(result['url']),
      bibYear: asString(result['bib_year']),
      matchedYear: asString(result['matched_year']).isEmpty
          ? asString(result['year'])
          : asString(result['matched_year']),
      bibAuthors: asString(result['bib_authors']),
      matchedAuthors: asString(result['matched_authors']).isEmpty
          ? asString(result['authors'])
          : asString(result['matched_authors']),
      missingAuthors: asString(result['missing_authors']),
      extraAuthors: asString(result['extra_authors']),
      bibAuthorCount: asInt(result['bib_author_count']),
      matchedAuthorCount: asInt(result['matched_author_count']),
      matchedVenue: asString(result['venue']),
      matchedType: asString(result['type']),
      webEvidence: asString(result['web_evidence']).toLowerCase() == 'yes' ||
          asString(result['web_evidence']).toLowerCase() == 'true' ||
          asString(result['evidence_kind']).toLowerCase() == 'web',
      evidenceKind: asString(result['evidence_kind']),
      webEvidenceNote: asString(result['web_evidence_note']),
      webEvidenceLinks: asString(result['web_evidence_links']),
      webEvidenceResults: asString(result['web_evidence_results']),
      snippet: asString(result['snippet']),
    );
  }

  EntryResult copyWith({
    String? key,
    String? title,
    String? status,
    bool? needsReview,
    String? riskLevel,
    int? confidenceScore,
    String? suggestedAction,
    String? source,
    double? similarity,
    String? reason,
    String? matchedTitle,
    String? riskExplanation,
    String? fixSuggestion,
    String? fixSuggestionBasis,
    String? parser,
    String? parserNote,
    String? parserConfidence,
    String? parserWarning,
    String? llmParseMode,
    int? candidateCount,
    String? arbitrationReason,
    String? sourceTrace,
    String? searchMode,
    String? sourceOrder,
    String? actualQueryTrace,
    String? adoptedSource,
    String? doiCheckStatus,
    String? doiCheckMessage,
    String? doiResolvedUrl,
    String? doiTargetTitle,
    String? doiTargetYear,
    String? doiTargetDoi,
    String? alternativeCandidates,
    String? candidateConflict,
    bool? standardCitationAvailable,
    String? standardCitationBasis,
    String? standardCitationApa,
    String? standardCitationBibtex,
    String? standardCitationGbt7714,
    String? authorCheck,
    String? authorReason,
    String? yearCheck,
    String? yearReason,
    String? doiCheck,
    String? doiReason,
    String? bibDoi,
    String? matchedDoi,
    String? bibUrl,
    String? matchedUrl,
    String? bibYear,
    String? matchedYear,
    String? bibAuthors,
    String? matchedAuthors,
    String? missingAuthors,
    String? extraAuthors,
    int? bibAuthorCount,
    int? matchedAuthorCount,
    String? matchedVenue,
    String? matchedType,
    bool? webEvidence,
    String? evidenceKind,
    String? webEvidenceNote,
    String? webEvidenceLinks,
    String? webEvidenceResults,
    String? snippet,
  }) {
    return EntryResult(
      key: key ?? this.key,
      title: title ?? this.title,
      status: status ?? this.status,
      needsReview: needsReview ?? this.needsReview,
      riskLevel: riskLevel ?? this.riskLevel,
      confidenceScore: confidenceScore ?? this.confidenceScore,
      suggestedAction: suggestedAction ?? this.suggestedAction,
      source: source ?? this.source,
      similarity: similarity ?? this.similarity,
      reason: reason ?? this.reason,
      matchedTitle: matchedTitle ?? this.matchedTitle,
      riskExplanation: riskExplanation ?? this.riskExplanation,
      fixSuggestion: fixSuggestion ?? this.fixSuggestion,
      fixSuggestionBasis: fixSuggestionBasis ?? this.fixSuggestionBasis,
      parser: parser ?? this.parser,
      parserNote: parserNote ?? this.parserNote,
      parserConfidence: parserConfidence ?? this.parserConfidence,
      parserWarning: parserWarning ?? this.parserWarning,
      llmParseMode: llmParseMode ?? this.llmParseMode,
      candidateCount: candidateCount ?? this.candidateCount,
      arbitrationReason: arbitrationReason ?? this.arbitrationReason,
      sourceTrace: sourceTrace ?? this.sourceTrace,
      searchMode: searchMode ?? this.searchMode,
      sourceOrder: sourceOrder ?? this.sourceOrder,
      actualQueryTrace: actualQueryTrace ?? this.actualQueryTrace,
      adoptedSource: adoptedSource ?? this.adoptedSource,
      doiCheckStatus: doiCheckStatus ?? this.doiCheckStatus,
      doiCheckMessage: doiCheckMessage ?? this.doiCheckMessage,
      doiResolvedUrl: doiResolvedUrl ?? this.doiResolvedUrl,
      doiTargetTitle: doiTargetTitle ?? this.doiTargetTitle,
      doiTargetYear: doiTargetYear ?? this.doiTargetYear,
      doiTargetDoi: doiTargetDoi ?? this.doiTargetDoi,
      alternativeCandidates:
          alternativeCandidates ?? this.alternativeCandidates,
      candidateConflict: candidateConflict ?? this.candidateConflict,
      standardCitationAvailable:
          standardCitationAvailable ?? this.standardCitationAvailable,
      standardCitationBasis:
          standardCitationBasis ?? this.standardCitationBasis,
      standardCitationApa: standardCitationApa ?? this.standardCitationApa,
      standardCitationBibtex:
          standardCitationBibtex ?? this.standardCitationBibtex,
      standardCitationGbt7714:
          standardCitationGbt7714 ?? this.standardCitationGbt7714,
      authorCheck: authorCheck ?? this.authorCheck,
      authorReason: authorReason ?? this.authorReason,
      yearCheck: yearCheck ?? this.yearCheck,
      yearReason: yearReason ?? this.yearReason,
      doiCheck: doiCheck ?? this.doiCheck,
      doiReason: doiReason ?? this.doiReason,
      bibDoi: bibDoi ?? this.bibDoi,
      matchedDoi: matchedDoi ?? this.matchedDoi,
      bibUrl: bibUrl ?? this.bibUrl,
      matchedUrl: matchedUrl ?? this.matchedUrl,
      bibYear: bibYear ?? this.bibYear,
      matchedYear: matchedYear ?? this.matchedYear,
      bibAuthors: bibAuthors ?? this.bibAuthors,
      matchedAuthors: matchedAuthors ?? this.matchedAuthors,
      missingAuthors: missingAuthors ?? this.missingAuthors,
      extraAuthors: extraAuthors ?? this.extraAuthors,
      bibAuthorCount: bibAuthorCount ?? this.bibAuthorCount,
      matchedAuthorCount: matchedAuthorCount ?? this.matchedAuthorCount,
      matchedVenue: matchedVenue ?? this.matchedVenue,
      matchedType: matchedType ?? this.matchedType,
      webEvidence: webEvidence ?? this.webEvidence,
      evidenceKind: evidenceKind ?? this.evidenceKind,
      webEvidenceNote: webEvidenceNote ?? this.webEvidenceNote,
      webEvidenceLinks: webEvidenceLinks ?? this.webEvidenceLinks,
      webEvidenceResults: webEvidenceResults ?? this.webEvidenceResults,
      snippet: snippet ?? this.snippet,
    );
  }
}

class ApiKeyTestResult {
  const ApiKeyTestResult({
    required this.source,
    required this.name,
    required this.ok,
    required this.status,
    required this.message,
    required this.endpoint,
    required this.statusCode,
    required this.records,
  });

  final String source;
  final String name;
  final bool ok;
  final String status;
  final String message;
  final String endpoint;
  final String statusCode;
  final int? records;

  factory ApiKeyTestResult.fromJson(Map<String, dynamic> json) {
    final rawRecords = json['records'];
    return ApiKeyTestResult(
      source: asString(json['source']),
      name: asString(json['name']),
      ok: json['ok'] == true || asString(json['ok']).toLowerCase() == 'true',
      status: asString(json['status']),
      message: asString(json['message']),
      endpoint: asString(json['endpoint']),
      statusCode: asString(json['status_code']),
      records: rawRecords == null || asString(rawRecords).isEmpty
          ? null
          : asInt(rawRecords),
    );
  }
}

class BackendCommand {
  const BackendCommand({required this.executable, this.scriptPath});

  final String executable;
  final String? scriptPath;
}
