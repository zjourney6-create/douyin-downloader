@echo off
chcp 65001 >nul
title 抖音无水印原流下载器
cd /d "%~dp0"
echo 正在启动 抖音无水印原流下载器...
start "" pythonw run.py
exit
