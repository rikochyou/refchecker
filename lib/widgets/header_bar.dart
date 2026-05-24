import 'package:flutter/material.dart';

import '../app_info.dart';
import '../models.dart';

class HeaderBar extends StatelessWidget {
  const HeaderBar({
    super.key,
    required this.canRun,
    required this.runState,
    required this.onRun,
  });

  final bool canRun;
  final RunState runState;
  final VoidCallback onRun;

  @override
  Widget build(BuildContext context) {
    final running = runState == RunState.running;
    return Container(
      height: 76,
      padding: const EdgeInsets.symmetric(horizontal: 20),
      decoration: const BoxDecoration(
        color: Colors.white,
        border: Border(bottom: BorderSide(color: Color(0xffd9ded6))),
      ),
      child: Row(
        children: [
          const Icon(Icons.fact_check_outlined, size: 32),
          const SizedBox(width: 12),
          const Expanded(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Text(
                      'RefChecker',
                      style:
                          TextStyle(fontSize: 24, fontWeight: FontWeight.w700),
                    ),
                    SizedBox(width: 8),
                    _VersionBadge(version: appVersion),
                  ],
                ),
                Text('BibTeX / DOCX AI 幻觉引用与元数据核验'),
              ],
            ),
          ),
          FilledButton.icon(
            onPressed: canRun ? onRun : null,
            icon: running
                ? const SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.play_arrow_rounded),
            label: Text(running ? '校验中' : '开始校验'),
          ),
        ],
      ),
    );
  }
}

class _VersionBadge extends StatelessWidget {
  const _VersionBadge({required this.version});

  final String version;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: const Color(0xffeef6f2),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: const Color(0xffd9ded6)),
      ),
      child: Text(
        'v$version',
        style: const TextStyle(
          color: Color(0xff596158),
          fontSize: 12,
          fontWeight: FontWeight.w700,
        ),
      ),
    );
  }
}
