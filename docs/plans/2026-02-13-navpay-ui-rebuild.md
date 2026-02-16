# NavPay UI 1:1 复刻（基于 MovPay 截图）Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将 `navpay-android/` Android 客户端界面与流程全部推倒重做，严格按 `navpay-android/docs/navpay_app_workflow.md` 与 `ref/navpay/*.png` 进行 1:1 复刻（不做交互与视觉创新）。

**Architecture:** 保持 Android 原生（Kotlin + XML Views + Fragments + ViewBinding），以“页面状态机 + API 适配层”的方式逐屏落地；用截图回归测试（Paparazzi）约束像素级 UI 变更；以 Navigation Component 管理复杂流程（启动/引导/注册/主 Tab/详情页）。

**Tech Stack:** Kotlin, Android Gradle, Fragments, ViewBinding, Material Components, ConstraintLayout/RecyclerView, Coroutines, OkHttp；新增：AndroidX Navigation, ViewModel + StateFlow, Paparazzi（截图测试），Coil（图片加载）。

---

## 结论：是否要用 Flutter

- 不需要。
- 目标是 Android 端 1:1 复刻 UI；Flutter 只是原 App 的实现方式，不是结果要求。
- 本仓库 `navpay-android/` 已是 Android Kotlin（`viewBinding true`、XML + Fragment），引入 Flutter 等同于新建一套构建链路、重写导航/网络/生命周期，风险与成本显著上升。
- 只有在“未来必须同时做 iOS 且要求完全一致 UI/逻辑复用”时，Flutter 才值得考虑；当前需求不满足该前提。

## 工作区/分支约束（先做准备）

- 本计划默认在 `navpay-android/` 子仓库下工作（`navpay-android/.git` 存在）。
- 建议使用独立 worktree 或新分支（writing-plans 要求来自 brainstorming 的 worktree；若你不需要 worktree，可直接新分支）。

---

## Task 1: 建立 UI 复刻基线与资源约束

**Files:**
- Read: `navpay-android/docs/navpay_app_workflow.md`
- Read: `ref/navpay/*.png`
- Create: `navpay-android/docs/ui/ui_spec.md`

**Step 1: 写“失败的校验”文档约束（先定义验收）**

在 `navpay-android/docs/ui/ui_spec.md` 写清楚：
- 每个页面对应的截图文件名
- 必须对齐的元素：字号、颜色、圆角、间距、按钮高度、阴影、Tab 样式
- 允许的偏差：字体家族差异（仅限系统字体）、状态栏图标

**Step 2: 运行校验脚本（此时不存在，预期失败）**

Run: `cd navpay-android && ./gradlew :app:testDebugUnitTest`
Expected: PASS（当前项目已有单测）；UI 复刻验收暂未接入，记录现状。

**Step 3: 写最小实现**

把 `navpay-android/docs/ui/ui_spec.md` 填完整（逐图映射页面名、路由名）。

**Step 4: 自检**

Run: `ls -la navpay-android/docs/ui/ui_spec.md`
Expected: 文件存在。

**Step 5: Commit**

```bash
cd navpay-android
git add docs/ui/ui_spec.md
git commit -m "docs(ui): add 1:1 ui spec and screenshot mapping"
```

---

## Task 2: 引入 Paparazzi 截图测试（为 1:1 提供回归手段）

**Files:**
- Modify: `navpay-android/app/build.gradle`
- Create: `navpay-android/app/src/test/java/com/phonepe/checksumclient/ui/PaparazziSmokeTest.kt`

**Step 1: 写失败的测试（先引用 Paparazzi，确保编译失败）**

```kotlin
// navpay-android/app/src/test/java/com/phonepe/checksumclient/ui/PaparazziSmokeTest.kt
package com.phonepe.checksumclient.ui

import app.cash.paparazzi.Paparazzi
import org.junit.Rule
import org.junit.Test

class PaparazziSmokeTest {
  @get:Rule val paparazzi = Paparazzi()

  @Test fun smoke() {
    // placeholder
  }
}
```

**Step 2: 运行测试确认失败**

Run: `cd navpay-android && ./gradlew :app:testDebugUnitTest`
Expected: FAIL（找不到 Paparazzi 依赖）。

**Step 3: 最小实现（接入 Paparazzi）**

在 `navpay-android/app/build.gradle` 添加 Paparazzi 插件/依赖（按 Paparazzi 官方 Gradle 用法）。

**Step 4: 运行测试确认通过**

Run: `cd navpay-android && ./gradlew :app:testDebugUnitTest`
Expected: PASS。

**Step 5: Commit**

```bash
cd navpay-android
git add app/build.gradle app/src/test/java/com/phonepe/checksumclient/ui/PaparazziSmokeTest.kt
git commit -m "test(ui): add paparazzi baseline"
```

---

## Task 3: 定义主题资源（颜色/圆角/字体/按钮高度）

**Files:**
- Modify: `navpay-android/app/src/main/res/values/colors.xml`
- Create: `navpay-android/app/src/main/res/values/dimens_movpay.xml`
- Create: `navpay-android/app/src/main/res/values/styles_movpay.xml`

**Step 1: 写失败的 Paparazzi 测试（渲染一个按钮卡片）**

Create: `navpay-android/app/src/test/java/com/phonepe/checksumclient/ui/MovpayThemeSnapshotTest.kt`
- 断言：截图生成成功（先让它失败，引用不存在的 style/dimen）。

**Step 2: 运行测试确认失败**

Run: `cd navpay-android && ./gradlew :app:testDebugUnitTest`
Expected: FAIL（资源不存在）。

**Step 3: 最小实现（补齐资源）**

- 从截图提取关键色：主蓝、浅灰背景、分割线灰、文字灰。
- 在 `dimens_movpay.xml` 固化：圆角（如 12dp/16dp）、按钮高度（如 48dp/52dp）、页面 padding（16dp）等。
- 在 `styles_movpay.xml` 定义：主按钮、次按钮、输入框、toolbar 文字。

**Step 4: 运行测试确认通过**

Run: `cd navpay-android && ./gradlew :app:testDebugUnitTest`
Expected: PASS（生成快照）。

**Step 5: Commit**

```bash
cd navpay-android
git add app/src/main/res/values/colors.xml app/src/main/res/values/dimens_movpay.xml app/src/main/res/values/styles_movpay.xml app/src/test/java/com/phonepe/checksumclient/ui/MovpayThemeSnapshotTest.kt
git commit -m "feat(ui): add movpay-like theme tokens"
```

---

## Task 4: 导航架构改造为单 Activity + NavHost（支撑复杂流程）

**Files:**
- Modify: `navpay-android/app/build.gradle`
- Modify: `navpay-android/app/src/main/res/layout/activity_main.xml`
- Modify: `navpay-android/app/src/main/java/com/phonepe/checksumclient/MainActivity.kt`
- Create: `navpay-android/app/src/main/res/navigation/nav_graph.xml`

**Step 1: 写失败的测试（验证 nav_graph 存在并可解析）**

Create: `navpay-android/app/src/test/java/com/phonepe/checksumclient/nav/NavGraphParseTest.kt`
- 加载 `R.navigation.nav_graph`（先失败，因为文件不存在/依赖未加）。

**Step 2: 运行测试确认失败**

Run: `cd navpay-android && ./gradlew :app:testDebugUnitTest`
Expected: FAIL。

**Step 3: 最小实现**

- 添加 Navigation 依赖。
- 新建 `nav_graph.xml`，至少包含：`SplashFragment`（占位）、`MainTabsFragment`（占位）。
- `activity_main.xml` 改为 `FragmentContainerView`（NavHost）。
- `MainActivity.kt` 改为由 Navigation 驱动。

**Step 4: 运行测试确认通过**

Run: `cd navpay-android && ./gradlew :app:testDebugUnitTest`
Expected: PASS。

**Step 5: Commit**

```bash
cd navpay-android
git add app/build.gradle app/src/main/res/layout/activity_main.xml app/src/main/java/com/phonepe/checksumclient/MainActivity.kt app/src/main/res/navigation/nav_graph.xml app/src/test/java/com/phonepe/checksumclient/nav/NavGraphParseTest.kt
git commit -m "refactor(nav): migrate to navhost + nav graph"
```

---

## Task 5: 复刻启动页与引导页（02-04）

**Files:**
- Create: `navpay-android/app/src/main/java/com/phonepe/checksumclient/ui/splash/SplashFragment.kt`
- Create: `navpay-android/app/src/main/res/layout/fragment_splash.xml`
- Create: `navpay-android/app/src/main/java/com/phonepe/checksumclient/ui/onboarding/OnboardingFragment.kt`
- Create: `navpay-android/app/src/main/res/layout/fragment_onboarding.xml`
- Modify: `navpay-android/app/src/main/res/navigation/nav_graph.xml`
- Test: `navpay-android/app/src/test/java/com/phonepe/checksumclient/ui/SplashSnapshotTest.kt`

**Step 1: 写失败的 Paparazzi 测试（Splash 1:1）**

- 以 `02_启动页_MovPay.png` 为目标：居中 Logo + 标题/副标题。

**Step 2: 运行测试确认失败**

Run: `cd navpay-android && ./gradlew :app:testDebugUnitTest`
Expected: FAIL（Fragment/layout 不存在）。

**Step 3: 最小实现**

- Splash：静态布局 + 背景。
- Onboarding：ViewPager2/RecyclerView Pager + indicator + 底部按钮（Next/Register/Login），按截图做 1:1。
- 路由：App 启动先到 Splash，再到 Onboarding。

**Step 4: 运行测试确认通过**

Run: `cd navpay-android && ./gradlew :app:testDebugUnitTest`
Expected: PASS（生成快照）。

**Step 5: Commit**

```bash
cd navpay-android
git add app/src/main/java/com/phonepe/checksumclient/ui/splash/SplashFragment.kt app/src/main/res/layout/fragment_splash.xml app/src/main/java/com/phonepe/checksumclient/ui/onboarding/OnboardingFragment.kt app/src/main/res/layout/fragment_onboarding.xml app/src/main/res/navigation/nav_graph.xml app/src/test/java/com/phonepe/checksumclient/ui/SplashSnapshotTest.kt
git commit -m "feat(ui): recreate splash + onboarding screens"
```

---

## Task 6: 复刻注册页与 OTP 弹窗（05-06）

**Files:**
- Create: `navpay-android/app/src/main/java/com/phonepe/checksumclient/ui/auth/RegisterFragment.kt`
- Create: `navpay-android/app/src/main/res/layout/fragment_register.xml`
- Create: `navpay-android/app/src/main/res/layout/dialog_otp.xml`
- Modify: `navpay-android/app/src/main/res/navigation/nav_graph.xml`
- Test: `navpay-android/app/src/test/java/com/phonepe/checksumclient/ui/RegisterSnapshotTest.kt`

步骤同上：
- 先写失败快照测试
- 跑失败
- 实现 1:1 布局（输入框样式/眼睛 icon/邀请码长度提示/按钮）
- 再跑通过
- Commit

---

## Task 7: 主 Tab 结构改为 4 Tab（Home/Buy RP/Sell RP/Mine）并 1:1 复刻底栏

**Files:**
- Create: `navpay-android/app/src/main/java/com/phonepe/checksumclient/ui/tabs/MainTabsFragment.kt`
- Create: `navpay-android/app/src/main/res/layout/fragment_main_tabs.xml`
- Create: `navpay-android/app/src/main/res/menu/bottom_nav_movpay.xml`
- Modify: `navpay-android/app/src/main/res/navigation/nav_graph.xml`
- Test: `navpay-android/app/src/test/java/com/phonepe/checksumclient/ui/BottomNavSnapshotTest.kt`

---

## Task 8: Home 页（14-16、11、13、15、16 的组合）

**Files:**
- Create: `navpay-android/app/src/main/java/com/phonepe/checksumclient/ui/home/HomeFragment.kt`
- Create: `navpay-android/app/src/main/res/layout/fragment_home.xml`
- Create: `navpay-android/app/src/main/res/layout/item_tutorial_entry.xml`
- Test: `navpay-android/app/src/test/java/com/phonepe/checksumclient/ui/HomeSnapshotTest.kt`

实现顺序：
- Banner 区
- 统计卡片（Buy quantity/Buy amount/Sell today/Total revenue）
- Tutorial 列表
- 进入 Daily details

---

## Task 9: 新手奖励页（11、13）

**Files:**
- Create: `navpay-android/app/src/main/java/com/phonepe/checksumclient/ui/rewards/NewbieRewardsFragment.kt`
- Create: `navpay-android/app/src/main/res/layout/fragment_newbie_rewards.xml`
- Test: `navpay-android/app/src/test/java/com/phonepe/checksumclient/ui/NewbieRewardsSnapshotTest.kt`

---

## Task 10: 教程轮播页（08-10、12）

**Files:**
- Create: `navpay-android/app/src/main/java/com/phonepe/checksumclient/ui/tutorial/TutorialFragment.kt`
- Create: `navpay-android/app/src/main/res/layout/fragment_tutorial.xml`
- Test: `navpay-android/app/src/test/java/com/phonepe/checksumclient/ui/TutorialSnapshotTest.kt`

---

## Task 11: Sell RP 页（17、37）与 Add Wallet

**Files:**
- Create: `navpay-android/app/src/main/java/com/phonepe/checksumclient/ui/sell/SellRpFragment.kt`
- Create: `navpay-android/app/src/main/res/layout/fragment_sell_rp.xml`
- Create: `navpay-android/app/src/main/res/layout/dialog_add_wallet.xml`
- Test: `navpay-android/app/src/test/java/com/phonepe/checksumclient/ui/SellRpSnapshotTest.kt`

---

## Task 12: Mine 页（19）

**Files:**
- Create: `navpay-android/app/src/main/java/com/phonepe/checksumclient/ui/mine/MineFragment.kt`
- Create: `navpay-android/app/src/main/res/layout/fragment_mine.xml`
- Test: `navpay-android/app/src/test/java/com/phonepe/checksumclient/ui/MineSnapshotTest.kt`

---

## Task 13: 指定支付 App 列表与下载弹窗（20-21）

**Files:**
- Create: `navpay-android/app/src/main/java/com/phonepe/checksumclient/ui/paymentapps/PaymentAppsFragment.kt`
- Create: `navpay-android/app/src/main/res/layout/fragment_payment_apps.xml`
- Create: `navpay-android/app/src/main/res/layout/dialog_download_progress.xml`
- Test: `navpay-android/app/src/test/java/com/phonepe/checksumclient/ui/PaymentAppsSnapshotTest.kt`

说明：这里只做 UI 1:1 与交互壳；真实下载/安装流程后续再接。

---

## Task 14: Buy RP 订单大厅（18、29-33、35、22、39）

**Files:**
- Create: `navpay-android/app/src/main/java/com/phonepe/checksumclient/ui/buy/BuyRpFragment.kt`
- Create: `navpay-android/app/src/main/res/layout/fragment_buy_rp.xml`
- Create: `navpay-android/app/src/main/res/layout/item_buy_rp_order.xml`
- Create: `navpay-android/app/src/main/res/layout/bottomsheet_select_payment_method.xml`
- Test: `navpay-android/app/src/test/java/com/phonepe/checksumclient/ui/BuyRpSnapshotTest.kt`

实现顺序：
- 顶部 L1-L7 Chip/Tab
- 订单卡片（ID/Amount/Award/Receive 按钮）
- Receive -> 选择支付方式 bottom sheet
- 错误 toast/弹层（订单被占用）

---

## Task 15: 支付任务页与锁单/提交 UTR（23-28、40）

**Files:**
- Create: `navpay-android/app/src/main/java/com/phonepe/checksumclient/ui/task/PaymentTaskFragment.kt`
- Create: `navpay-android/app/src/main/res/layout/fragment_payment_task.xml`
- Create: `navpay-android/app/src/main/res/layout/dialog_go_to_payment.xml`
- Create: `navpay-android/app/src/main/res/layout/dialog_lock_order.xml`
- Create: `navpay-android/app/src/main/res/layout/dialog_submit_utr.xml`
- Test: `navpay-android/app/src/test/java/com/phonepe/checksumclient/ui/PaymentTaskSnapshotTest.kt`

实现顺序：
- 页面静态布局 1:1（倒计时、金额、收款信息、两个按钮）
- Go to payment 二次确认弹窗
- Lock order 弹窗 + 锁单状态 UI
- Submit UTR 弹窗（12 位输入提示）

---

## Task 16: Buy RP record（34、38）

**Files:**
- Create: `navpay-android/app/src/main/java/com/phonepe/checksumclient/ui/records/BuyRpRecordFragment.kt`
- Create: `navpay-android/app/src/main/res/layout/fragment_buy_rp_record.xml`
- Create: `navpay-android/app/src/main/res/layout/item_buy_rp_record.xml`
- Test: `navpay-android/app/src/test/java/com/phonepe/checksumclient/ui/BuyRpRecordSnapshotTest.kt`

---

## Task 17: Points details（36、41）

**Files:**
- Create: `navpay-android/app/src/main/java/com/phonepe/checksumclient/ui/points/PointsDetailsFragment.kt`
- Create: `navpay-android/app/src/main/res/layout/fragment_points_details.xml`
- Create: `navpay-android/app/src/main/res/layout/item_point_detail.xml`
- Test: `navpay-android/app/src/test/java/com/phonepe/checksumclient/ui/PointsDetailsSnapshotTest.kt`

---

## Task 18: Telegram 绑定入口（42-44）

**Files:**
- Create: `navpay-android/app/src/main/java/com/phonepe/checksumclient/ui/channel/OfficialChannelFragment.kt`
- Create: `navpay-android/app/src/main/res/layout/fragment_official_channel.xml`
- Test: `navpay-android/app/src/test/java/com/phonepe/checksumclient/ui/OfficialChannelSnapshotTest.kt`

说明：先做 UI + 外链跳转壳；Bot 绑定与审核状态后续接服务端。

---

## Task 19: 设计并替换 NavPay App Icon 与启动图标

**Files:**
- Create: `navpay-android/docs/design/navpay_icon.svg`
- Modify: `navpay-android/app/src/main/res/mipmap-anydpi-v26/ic_launcher.xml`
- Modify: `navpay-android/app/src/main/res/mipmap-anydpi-v26/ic_launcher_round.xml`
- Modify: `navpay-android/app/src/main/res/drawable/ic_launcher_foreground.xml`
- Modify: `navpay-android/app/src/main/res/values/colors.xml`

约束：
- 只做一个简洁的标记（建议：圆角方底 + “N”/“Nav” + 支付箭头），保证小尺寸清晰。
- adaptive icon 前景用 vector（`ic_launcher_foreground.xml`），背景用纯色。

---

## Task 20: 端到端流程冒烟（手动 + 自动）

**Files:**
- Modify: `navpay-android/docs/navpay_app_workflow.md`（补充“NavPay 已实现到哪一步”的对照表）

**Step 1: 写失败的检查清单**

在文档里列出每个页面：是否已 1:1、是否已接真实数据、是否仅 UI 壳。

**Step 2: 运行单测/快照**

Run:
- `cd navpay-android && ./gradlew :app:testDebugUnitTest`
Expected: PASS。

**Step 3: 手动冒烟**

Run:
- `cd navpay-android && ./gradlew :app:assembleDebug`
Expected: BUILD SUCCESSFUL。

**Step 4: Commit**

```bash
cd navpay-android
git add docs/navpay_app_workflow.md
git commit -m "docs: add ui rebuild progress checklist"
```

---

## 备注：关于图片素材

- 引导页/教程页中用到的插画，如果无法从现有资源获取：
  - 优先从 `ref/navpay/*.png` 截图中裁切出插画区域，存入 `navpay-android/app/src/main/res/drawable-nodpi/`。
  - 保持与截图一致的比例与边距，以服务 1:1 复刻目标。

## 验收标准（硬性）

- 每个页面至少 1 张 Paparazzi 快照与对应截图比对（人工审查）。
- 主流程可点通：启动/引导/注册/进入主 Tab/进入 BuyRP/进入支付任务页/锁单与 UTR 弹窗/查看记录与积分。
- 视觉不做自创改动：颜色、圆角、按钮样式、字体大小、Tab 结构必须跟截图一致。

