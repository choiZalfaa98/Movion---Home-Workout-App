from PyQt6.QtWidgets import QStackedWidget
from PyQt6.QtCore import QTimer, QEvent

from views.page_constants import Page
from views.base_window import BaseWindow
from views.splash_screen import SplashScreen
from views.login_page import LoginPage
from views.forgot_pass import ForgotPassword
from views.signup_page import SignUp
from views.profile_setup import ProfileSetup
from views.home_page import HomePage
from views.workout_page import WorkoutPage
from views.tracking_page import TrackingMode
from views.warmcool_tips import WarmCoolPage
from views.fill_person2_details import FillPerson2Details
from views.workout_result import WorkoutResult
from views.workout_history import WorkoutHistory
from views.workout_history_full import WorkoutHistoryFull
from views.profile_page import ProfilePage
from views.confirmation_pages import (
    LogoutConfirmationPage,
    EndWorkoutConfirmationPage,
    PauseWorkoutPage,
    ResetPasswordSentPage,
)

from services.session_service import load_session, get_current_session
from services.auth_service import logout_user
from services.workout_guide_helper import get_workout_guide
from services.profile_service import get_profile
from workout_app_guideline.sessions.workout_session import WorkoutSessionTemp
from services.workout_report_service import (
    create_workout_session,
    complete_workout_session,
    cancel_workout_session,
    fail_workout_session
)


class AppWindow(BaseWindow):
    """
    Main application window and navigation coordinator.

    This class manages:
    - page creation, registration, and stacked-widget navigation;
    - startup bootstrapping and lazy loading for resource-heavy pages;
    - signal connections between authentication, profile, and workout views;
    - user session restoration and logout handling;
    - workout lifecycle transitions, including preparation, pause, resume,
      completion, cancellation, and report upload;
    - camera and backend cleanup when the application closes.
    """

    def __init__(self):
        super().__init__()

        self.current_user_id = None
        self.workout_session_temp = WorkoutSessionTemp()
        self.stack = QStackedWidget()

        self.pages = {
            Page.SPLASH: SplashScreen(),
        }

        self.stack.addWidget(self.pages[Page.SPLASH])
        self.setCentralWidget(self.stack)
        self.navigate(Page.SPLASH)

        self._boot_queue = []
        self._boot_index = 0

        self._boot_scheduled = False
        self._boot_started = False
        self._boot_finished = False
        self._signals_connected = False
        self._pending_stack_pages = []

        self._lazy_page_factories = {
            Page.WORKOUT_GUIDE: self._create_workout_guide_page,
            Page.WORKOUT_SESSION: self._create_workout_session_page,
        }

        self._lazy_signals_connected = set()

        self._pending_workout_session = None
        self._pending_workout_action = None

    def showEvent(self, event):
        super().showEvent(event)
        self._schedule_bootstrap_when_window_visible()

    def changeEvent(self, event):
        super().changeEvent(event)

        if event.type() == QEvent.Type.WindowStateChange:
            self._schedule_bootstrap_when_window_visible()

    def _schedule_bootstrap_when_window_visible(self):
        if self._boot_finished or self._boot_started or self._boot_scheduled:
            return

        if self.isMinimized():
            return

        self._boot_scheduled = True

        splash = self.pages.get(Page.SPLASH)
        if hasattr(splash, "set_loading_progress"):
            splash.set_loading_progress(0, "Preparing MOVION...")

        QTimer.singleShot(1500, self._start_bootstrap)

    def _start_bootstrap(self):
        if self._boot_finished or self._boot_started:
            return

        if self.isMinimized():
            self._boot_scheduled = False
            return

        self._boot_started = True
        self._boot_scheduled = False

        self._boot_queue = [
            (Page.LOGIN, lambda: LoginPage()),
            (Page.FORGOT_PASS, lambda: ForgotPassword()),
            (Page.SIGNUP, lambda: SignUp()),
            (Page.PROFILE_SETUP, lambda: ProfileSetup()),

            (Page.HOME, lambda: HomePage(self.navigate)),
            (Page.WORKOUT_PREVIEW, lambda: WorkoutPage(self.navigate)),
            (Page.TRACKING_MODE, lambda: TrackingMode(self.navigate)),
            (Page.WARM_COOL_PAGE, lambda: WarmCoolPage()),
            (Page.FILL_PERSON2_DETAILS, lambda: FillPerson2Details()),
            (Page.WORKOUT_RESULT, lambda: WorkoutResult()),

            (Page.WORKOUT_HISTORY, lambda: WorkoutHistory(self.navigate)),
            (Page.WORKOUT_HISTORY_FULL, lambda: WorkoutHistoryFull(self.navigate)),
            (Page.PROFILE, lambda: ProfilePage(self.navigate)),

            (Page.LOGOUT_CONFIRM, lambda: LogoutConfirmationPage()),
            (Page.END_WORKOUT_CONFIRM, lambda: EndWorkoutConfirmationPage()),
            (Page.PAUSE_WORKOUT, lambda: PauseWorkoutPage()),
            (Page.RESET_PASSWORD_SENT, lambda: ResetPasswordSentPage()),
        ]

        self._boot_index = 0
        self._pending_stack_pages = []

        splash = self.pages.get(Page.SPLASH)
        if hasattr(splash, "set_loading_progress"):
            splash.set_loading_progress(0, "Initializing pages...")

        QTimer.singleShot(30, self._bootstrap_next_page)

    def _bootstrap_next_page(self):
        if self._boot_index >= len(self._boot_queue):
            self._finish_bootstrap()
            return

        page_name, factory = self._boot_queue[self._boot_index]
        total = max(1, len(self._boot_queue))

        splash = self.pages.get(Page.SPLASH)

        try:
            before_progress = int((self._boot_index / total) * 100)

            if hasattr(splash, "set_loading_progress"):
                splash.set_loading_progress(
                    before_progress,
                    f"Loading {page_name}..."
                )

            page = factory()
            self.pages[page_name] = page

            self._pending_stack_pages.append(page_name)

            after_progress = int(((self._boot_index + 1) / total) * 100)

            if hasattr(splash, "set_loading_progress"):
                splash.set_loading_progress(
                    after_progress,
                    f"{page_name} ready"
                )

            #print("[BOOT_PAGE_READY]", page_name)

        except Exception as e:
            #print("[BOOT_PAGE_FAILED]", page_name, e)

            if hasattr(splash, "set_loading_progress"):
                splash.set_loading_progress(
                    100,
                    f"Failed loading {page_name}"
                )

            raise

        self._boot_index += 1

        QTimer.singleShot(30, self._bootstrap_next_page)

    def _attach_pending_pages_to_stack(self):
        current_widget = self.stack.currentWidget()

        self.stack.setUpdatesEnabled(False)

        for page_name in self._pending_stack_pages:
            page = self.pages.get(page_name)

            if page is None:
                continue

            if self.stack.indexOf(page) == -1:
                self.stack.addWidget(page)

        if current_widget is not None:
            self.stack.setCurrentWidget(current_widget)

        self.stack.setUpdatesEnabled(True)
        self.stack.update()

    def _finish_bootstrap(self):
        if self._boot_finished:
            return

        self._boot_finished = True

        splash = self.pages.get(Page.SPLASH)

        if hasattr(splash, "set_loading_progress"):
            splash.set_loading_progress(100, "Finishing setup...")

        self._connect_signals()

        #print("[BOOT_FINISHED] all pages initialized")

        QTimer.singleShot(1500, self.restore_session)

    def _create_workout_guide_page(self):
        from views.workout_guide import WorkoutGuide
        return WorkoutGuide()


    def _create_workout_session_page(self):
        from views.workout_in_session import WorkoutSession
        return WorkoutSession()


    def _get_or_create_page(self, page_name):
        page = self.pages.get(page_name)

        if page:
            return page

        factory = self._lazy_page_factories.get(page_name)

        if not factory:
            return None

        #print("[LAZY_PAGE_CREATE]", page_name)

        page = factory()
        self.pages[page_name] = page

        self._connect_lazy_page_signals(page_name, page)

        return page


    def _connect_lazy_page_signals(self, page_name, page):
        if page_name in self._lazy_signals_connected:
            return

        if page_name == Page.WORKOUT_GUIDE:
            page.back_or_pause.connect(self.pause_workout)
            page.begin_each_workout.connect(self.start_workout_session)
            page.workout_finished.connect(self.finish_workout)

        elif page_name == Page.WORKOUT_SESSION:
            page.back_or_pause.connect(self.pause_workout)
            page.workout_done.connect(self.handle_next_workout)
            page.backend_ready.connect(self._on_workout_backend_ready)
            page.backend_failed.connect(self._on_workout_backend_failed)

        self._lazy_signals_connected.add(page_name)

    def _connect_signals(self):
        if self._signals_connected:
            return

        self._signals_connected = True

        login_page = self.pages[Page.LOGIN]
        login_page.go_to_forgot.connect(lambda: self.navigate(Page.FORGOT_PASS))
        login_page.go_to_signup.connect(lambda: self.navigate(Page.SIGNUP))
        login_page.go_to_home.connect(self.handle_login_success)
        login_page.go_to_setup.connect(self.show_profile_setup)

        forgot_page = self.pages[Page.FORGOT_PASS]
        forgot_page.go_to_email_sent.connect(lambda: self.navigate(Page.RESET_PASSWORD_SENT))
        forgot_page.back_to_login.connect(lambda: self.navigate(Page.LOGIN))

        signup_page = self.pages[Page.SIGNUP]
        signup_page.go_to_setup.connect(self.show_profile_setup)
        signup_page.go_to_login.connect(lambda: self.navigate(Page.LOGIN))

        profile_setup = self.pages[Page.PROFILE_SETUP]
        profile_setup.continue_to_login.connect(lambda: self.navigate(Page.LOGIN))

        home_page = self.pages[Page.HOME]
        home_page.go_to_workout.connect(lambda: self.navigate(Page.WORKOUT_PREVIEW))

        workout_page = self.pages[Page.WORKOUT_PREVIEW]
        workout_page.continue_to_track_mode.connect(lambda: self.navigate(Page.TRACKING_MODE))

        tracking_page = self.pages[Page.TRACKING_MODE]
        tracking_page.continue_to_tips.connect(self.prepare_workout_session)

        warmcool_page = self.pages[Page.WARM_COOL_PAGE]
        warmcool_page.back_to_preview.connect(lambda: self.navigate(Page.TRACKING_MODE))
        warmcool_page.go_to_session.connect(self.go_to_first_guide)



        fill_person2 = self.pages[Page.FILL_PERSON2_DETAILS]
        fill_person2.generate_report.connect(self.finish_multi_report)

        workout_result = self.pages[Page.WORKOUT_RESULT]
        workout_result.back_to_home.connect(self.back_to_home_from_result)

        history_full = self.pages[Page.WORKOUT_HISTORY_FULL]
        history_full.back_to_history.connect(lambda: self.navigate(Page.WORKOUT_HISTORY))

        profile_page = self.pages[Page.PROFILE]
        profile_page.go_to_logout.connect(lambda: self.navigate(Page.LOGOUT_CONFIRM))

        logout_page = self.pages[Page.LOGOUT_CONFIRM]
        logout_page.confirmed.connect(self.handle_logout)
        logout_page.cancelled.connect(lambda: self.navigate(Page.PROFILE))

        end_workout_page = self.pages[Page.END_WORKOUT_CONFIRM]
        end_workout_page.confirmed.connect(self.handle_end_workout_confirmed)
        end_workout_page.cancelled.connect(lambda: self.navigate(Page.PAUSE_WORKOUT))

        pause_page = self.pages[Page.PAUSE_WORKOUT]
        pause_page.end_workout.connect(lambda: self.navigate(Page.END_WORKOUT_CONFIRM))
        pause_page.continue_workout.connect(self.resume_workout)

        reset_page = self.pages[Page.RESET_PASSWORD_SENT]
        reset_page.back_to_login.connect(lambda: self.navigate(Page.LOGIN))

    def _show_page_in_stack(self, page):
        if self.stack.currentWidget() is page:
            return

        if self.stack.indexOf(page) == -1:
            self.stack.setUpdatesEnabled(False)
            self.stack.addWidget(page)
            self.stack.setCurrentWidget(page)
            self.stack.setUpdatesEnabled(True)
            self.stack.update()
            return

        self.stack.setCurrentWidget(page)

    def navigate(self, page_name):
        page = self._get_or_create_page(page_name)

        if not page:
            return

        same_page = getattr(self, "_current_page", None) == page_name

        if not same_page:
            self._current_page = page_name
            self._show_page_in_stack(page)

        if hasattr(page, "sidebar"):
            page.sidebar.set_active_page(page_name)

        if page_name in (Page.HOME, Page.PROFILE) and hasattr(page, "set_user_id"):
            user_id = self.current_user_id
            QTimer.singleShot(
                0,
                lambda p=page, uid=user_id: p.set_user_id(uid)
            )

    def handle_login_success(self, user_id):
        self.current_user_id = user_id
        self.navigate(Page.HOME)

    def show_profile_setup(self, user_id):
        profile_setup = self.pages[Page.PROFILE_SETUP]
        profile_setup.set_user_id(user_id)
        self.navigate(Page.PROFILE_SETUP)

    def restore_session(self):
        if not load_session():
            self.current_user_id = None
            self.navigate(Page.LOGIN)
            return

        auth_session = get_current_session()

        if not auth_session or not auth_session.user:
            self.current_user_id = None
            self.navigate(Page.LOGIN)
            return

        self.current_user_id = auth_session.user.id
        self.navigate(Page.HOME)

    def handle_logout(self):
        result = logout_user()

        if result["success"]:
            self.current_user_id = None

            login_page = self.pages[Page.LOGIN]
            login_page.email_input.clear()
            login_page.password_input.clear()

            self.navigate(Page.LOGIN)
        else:
            print("Logout failed:", result["error"])

    def prepare_workout_session(self, mode, camera):
        session = self.workout_session_temp
        session.reset()
        session.set_config(mode, camera)

        auth_session = get_current_session()

        if auth_session and auth_session.user:
            profile = get_profile(auth_session.user.id)

            if profile["success"] and profile["exists"]:
                user_data = profile["data"]

                height_cm = user_data.get("height_cm")
                weight_kg = user_data.get("weight_kg")

                session.set_user1({
                    "id": user_data.get("id"),
                    "name": user_data.get("name", "User"),
                    "email": auth_session.user.email,
                    "age": user_data.get("age"),
                    "gender": user_data.get("gender"),
                    "height_cm": height_cm,
                    "weight_kg": weight_kg,

                    # Compatibility for existing CalorieCalculator.
                    "height": height_cm,
                    "weight": weight_kg,
                })

        session.set_workouts(get_workout_guide())

        try:
            session.current_page = "warmcool"
        except Exception:
            pass

        self._pending_workout_session = None
        self._pending_workout_action = None

        self.navigate(Page.WARM_COOL_PAGE)

    def show_profile(self):
        #print("SHOW PROFILE CALLED")

        profile_page = self.pages[Page.PROFILE]
        profile_page.set_user_id(self.current_user_id)

        self.navigate(Page.PROFILE)

    def go_to_first_guide(self):
        session = self.workout_session_temp

        if hasattr(session, "start_timer"):
            session.start_timer()

        if not getattr(session, "remote_session_id", None):
            create_result = create_workout_session(
                user_id=(session.user1 or {}).get("id"),
                mode=session.mode,
            )

            if create_result["success"]:
                session.set_remote_session_id(create_result["data"]["id"])
                #print("[REMOTE_SESSION_CREATED]", session.remote_session_id)
            else:
                print("[REMOTE_SESSION_CREATE_FAILED]", create_result["error"])

        try:
            session.current_page = "guide"
        except Exception:
            pass

        guide = self._get_or_create_page(Page.WORKOUT_GUIDE)
        guide.set_session(session)

        current = session.get_current_workout()

        """print(
        "[GO_TO_FIRST_GUIDE]",
        "index=", getattr(session, "current_index", None),
        "name=", current.get("name") if current else None,
        "label=", current.get("id") if current else None,
        )"""

        self.navigate(Page.WORKOUT_GUIDE)

        QTimer.singleShot(
            0,
            lambda s=session: self._prewarm_workout_lstm(s),
        )

    def _prewarm_workout_lstm(self, session):
        try:
            if getattr(session, "current_page", None) != "guide":
                return

            workout_page = self._get_or_create_page(Page.WORKOUT_SESSION)
            workout_page.prewarm_backends(session.mode)

        except Exception as exc:
            print("[PREWARM_WORKOUT_LSTM_WARN]", exc)

    def _stop_workout_camera(self):
        workout_page = self.pages.get(Page.WORKOUT_SESSION)

        if workout_page and hasattr(workout_page, "stop_camera"):
            try:
                workout_page.stop_camera()
            except Exception as e:
                print("[STOP_CAMERA_WARN]", e)

    def _should_mark_workout_failed_on_close(self):
        session = self.workout_session_temp

        remote_session_id = getattr(session, "remote_session_id", None)

        if not remote_session_id:
            return False

        if getattr(session, "report_uploaded", False):
            return False

        current_page = getattr(session, "current_page", None)

        if current_page is None:
            return False

        return True


    def _mark_workout_failed_on_close(self):
        session = self.workout_session_temp

        if not self._should_mark_workout_failed_on_close():
            return

        remote_session_id = getattr(session, "remote_session_id", None)

        fail_result = fail_workout_session(remote_session_id)

        if fail_result["success"]:
            print("[REMOTE_SESSION_FAILED_ON_CLOSE]", remote_session_id)
        else:
            print("[REMOTE_SESSION_FAIL_ON_CLOSE_FAILED]", fail_result["error"])

    def closeEvent(self, event):

        try:
            self._mark_workout_failed_on_close()
        except Exception as e:
            print("[CLOSE_EVENT_FAIL_MARK_WARN]", e)

        try:
            self._stop_workout_camera()
        except Exception as e:
            print("[CLOSE_EVENT_CAMERA_STOP_WARN]", e)

        super().closeEvent(event)

    def start_workout_session(self, session):
        workout_page = self._get_or_create_page(Page.WORKOUT_SESSION)

        if not workout_page.backends_ready_for(session.mode):
            self._pending_workout_session = session
            self._pending_workout_action = "start"
            self._set_workout_guide_backend_loading(True)
            workout_page.prewarm_backends(session.mode)

            """print(
                "[START_WAITING_FOR_BACKEND]",
                f"mode={session.mode}",
            )"""
            return

        self._enter_workout_session(workout_page, session)

    def _enter_workout_session(self, workout_page, session):
        if workout_page is None:
            return

        if not workout_page.backends_ready_for(session.mode):
            self._pending_workout_session = session
            self._pending_workout_action = "start"
            self._set_workout_guide_backend_loading(True)
            workout_page.prewarm_backends(session.mode)
            return

        if hasattr(workout_page, "hard_reset_for_new_workout"):
            workout_page.hard_reset_for_new_workout()

        if hasattr(workout_page, "ensure_camera_started"):
            camera_index = getattr(session, "camera", 0) or 0
            workout_page.ensure_camera_started(camera_index)

        started = workout_page.set_session(session)
        if started is False:
            self._pending_workout_session = session
            self._pending_workout_action = "start"
            self._set_workout_guide_backend_loading(True)
            return

        try:
            session.current_page = "session"
        except Exception:
            pass

        self._pending_workout_session = None
        self._pending_workout_action = None
        self._set_workout_guide_backend_loading(False)
        self.navigate(Page.WORKOUT_SESSION)

        current = session.get_current_workout()
        """print(
            "[START_WORKOUT_SESSION]",
            "index=", getattr(session, "current_index", None),
            "name=", current.get("name") if current else None,
            "label=", current.get("id") if current else None,
        )"""

    def _resume_workout_session(self, workout_page, session):
        if workout_page is None:
            return

        if not workout_page.backends_ready_for(session.mode):
            self._pending_workout_session = session
            self._pending_workout_action = "resume"
            workout_page.prewarm_backends(session.mode)
            return

        resumed = workout_page.resume(session)
        if resumed is False:
            self._pending_workout_session = session
            self._pending_workout_action = "resume"
            return

        self._pending_workout_session = None
        self._pending_workout_action = None
        self.navigate(Page.WORKOUT_SESSION)

    def _on_workout_backend_ready(self, payload):
        session = self._pending_workout_session
        action = self._pending_workout_action

        if session is None or action is None:
            return

        if action == "start":
            if getattr(session, "current_page", None) != "guide":
                self._pending_workout_session = None
                self._pending_workout_action = None
                self._set_workout_guide_backend_loading(False)
                return

            if getattr(self, "_current_page", None) != Page.WORKOUT_GUIDE:
                self._pending_workout_session = None
                self._pending_workout_action = None
                self._set_workout_guide_backend_loading(False)
                return

        workout_page = self.pages.get(Page.WORKOUT_SESSION)
        if workout_page is None or not workout_page.backends_ready_for(session.mode):
            return

        if action == "resume":
            QTimer.singleShot(
                0,
                lambda p=workout_page, s=session: self._resume_workout_session(p, s),
            )
        else:
            QTimer.singleShot(
                0,
                lambda p=workout_page, s=session: self._enter_workout_session(p, s),
            )

    def _on_workout_backend_failed(self, message):
        self._pending_workout_session = None
        self._pending_workout_action = None
        self._set_workout_guide_backend_loading(False)
        #print("[WORKOUT_BACKEND_FAILED]", message)

    def _set_workout_guide_backend_loading(self, loading: bool):
        guide = self.pages.get(Page.WORKOUT_GUIDE)
        if guide is not None and hasattr(guide, "set_backend_loading"):
            guide.set_backend_loading(bool(loading))

    def handle_next_workout(self):
        session = self.workout_session_temp

        if session.next_workout():
            try:
                session.current_page = "guide"
            except Exception:
                pass

            guide = self._get_or_create_page(Page.WORKOUT_GUIDE)
            guide.set_session(session)

            current = session.get_current_workout()

            """print(
                "[NEXT_WORKOUT_GUIDE]",
                "index=", getattr(session, "current_index", None),
                "name=", current.get("name") if current else None,
                "label=", current.get("id") if current else None,
            )"""

            self.navigate(Page.WORKOUT_GUIDE)
            return

        #print("[ALL_WORKOUTS_DONE]")
        self.finish_workout()

    def finish_workout(self):
        session = self.workout_session_temp

        if hasattr(session, "stop_timer"):
            session.stop_timer()

        self._stop_workout_camera()

        try:
            session.current_page = "result"
        except Exception:
            pass

        if session.mode == "multi":
            self.navigate(Page.FILL_PERSON2_DETAILS)
            return

        result_page = self.pages[Page.WORKOUT_RESULT]
        result_page.set_session(session)

        self._upload_completed_report_if_needed(
            report_data=result_page.report_data,
            user2=None,
        )

        self.navigate(Page.WORKOUT_RESULT)

    def pause_workout(self):
        session = self.workout_session_temp

        if hasattr(session, "pause_timer"):
            session.pause_timer()

        """print(
            "[PAUSE_WORKOUT]",
            "current_page=", getattr(session, "current_page", None),
            "duration=", session.get_duration_formatted() if hasattr(session, "get_duration_formatted") else None,
        )"""

        self.navigate(Page.PAUSE_WORKOUT)

    def resume_workout(self):
        session = self.workout_session_temp

        if hasattr(session, "resume_timer"):
            session.resume_timer()

        #print("RESUME - current_page:", session.current_page)
        #print("RESUME - remaining_guide_time:", session.remaining_guide_time)

        if session.current_page == "guide":
            guide = self._get_or_create_page(Page.WORKOUT_GUIDE)
            guide.set_session(session, resume=True)
            self.navigate(Page.WORKOUT_GUIDE)

        elif session.current_page == "session":
            workout = self._get_or_create_page(Page.WORKOUT_SESSION)

            if not workout.backends_ready_for(session.mode):
                self._pending_workout_session = session
                self._pending_workout_action = "resume"
                workout.prewarm_backends(session.mode)
                return

            self._resume_workout_session(workout, session)

        else:
            guide = self._get_or_create_page(Page.WORKOUT_GUIDE)
            guide.set_session(session)
            self.navigate(Page.WORKOUT_GUIDE)

    def handle_end_workout_confirmed(self):
        session = self.workout_session_temp

        if hasattr(session, "stop_timer"):
            session.stop_timer()

        cancel_result = cancel_workout_session(
            getattr(session, "remote_session_id", None)
        )

        if cancel_result["success"]:
            print("[REMOTE_SESSION_CANCELLED]")
        else:
            print("[REMOTE_SESSION_CANCEL_FAILED]", cancel_result["error"])

        workout_page = self.pages[Page.WORKOUT_SESSION]

        if workout_page and hasattr(workout_page, "stop_camera"):
            try:
                self._stop_workout_camera()
            except Exception as e:
                print("[STOP_CAMERA_WARN]", e)

        try:
            session.current_page = None
        except Exception:
            pass

        self.navigate(Page.HOME)

    def back_to_home_from_result(self):
        try:
            self.workout_session_temp.current_page = None
        except Exception:
            pass

        self.navigate(Page.HOME)

    def finish_multi_report(self, person2):
        session = self.workout_session_temp

        session.set_user2(person2)

        try:
            session.current_page = "result"
        except Exception:
            pass

        result_page = self.pages[Page.WORKOUT_RESULT]
        result_page.set_session(session)

        self._upload_completed_report_if_needed(
            report_data=result_page.report_data,
            user2=session.user2,
        )

        self.navigate(Page.WORKOUT_RESULT)

    def _upload_completed_report_if_needed(self, report_data, user2=None):
        session = self.workout_session_temp

        if getattr(session, "report_uploaded", False):
            #print("[WORKOUT_REPORT_UPLOAD_SKIPPED] already uploaded")
            return

        remote_session_id = getattr(session, "remote_session_id", None)

        if not remote_session_id:
            #print("[WORKOUT_REPORT_UPLOAD_SKIPPED] remote_session_id missing")
            return

        upload_result = complete_workout_session(
            session_id=remote_session_id,
            report_data=report_data,
            user1=session.user1,
            user2=user2,
        )

        if upload_result["success"]:
            if hasattr(session, "mark_report_uploaded"):
                session.mark_report_uploaded()
            else:
                session.report_uploaded = True

            #print("[WORKOUT_REPORT_UPLOADED]", remote_session_id)
        else:
            print("[WORKOUT_REPORT_UPLOAD_FAILED]", upload_result["error"])
