"""Stream control plane — управление 9 RTMP YouTube стримами через systemd.

Модули:
    systemd_manager: тонкая обёртка над systemctl (start/stop/restart/status/tail)
    provisioner:     генерация systemd unit + env + runner.sh из БД
    runner_template: шаблоны bash-скриптов для ffmpeg

Замена для Yii: SystemdService.php + StreamProvisionerService.php + YtController.
"""
