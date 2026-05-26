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
    required this.candidateCount,
    required this.arbitrationReason,
    required this.sourceTrace,
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
  final int candidateCount;
  final String arbitrationReason;
  final String sourceTrace;
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
      candidateCount: asInt(result['candidate_count']),
      arbitrationReason: asString(result['arbitration_reason']),
      sourceTrace: asString(result['source_trace']),
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
    int? candidateCount,
    String? arbitrationReason,
    String? sourceTrace,
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
      candidateCount: candidateCount ?? this.candidateCount,
      arbitrationReason: arbitrationReason ?? this.arbitrationReason,
      sourceTrace: sourceTrace ?? this.sourceTrace,
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
