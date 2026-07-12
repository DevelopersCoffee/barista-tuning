import 'package:slm_edge_intelligence/slm_edge_intelligence.dart';
import 'package:test/test.dart';

void main() {
  test('constructs public use-case models', () {
    const context = ExecutionContext(
      requestId: 'req-1',
      locale: LocaleContext(language: 'en', region: 'IN'),
      network: NetworkState.online,
    );

    const query = SearchQuery(
      text: 'play hindi news',
      constraints: {'genre': 'news'},
    );

    expect(context.requestId, 'req-1');
    expect(query.text, 'play hindi news');
  });

  test('mock client returns media candidates', () async {
    final edge = EdgeIntelligence.mock();

    const context = ExecutionContext(
      requestId: 'req-2',
      locale: LocaleContext(language: 'en', region: 'IN'),
      network: NetworkState.online,
    );

    final result = await edge.search(
      context,
      const SearchQuery(text: 'hindi news'),
    );

    expect(result.candidates, isNotEmpty);
    expect(result.traceId, 'req-2');
  });
}
