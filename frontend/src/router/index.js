import { createRouter, createWebHistory } from 'vue-router';
import { SITE_NAME } from '../constants/site';
import { useAuthStore } from '../stores/authStore';

const Home = () => import('../views/Home.vue');
const Login = () => import('../views/Login.vue');
const Dashboard = () => import('../views/Dashboard.vue');
const CampaignCreate = () => import('../views/CampaignCreate.vue');
const CampaignDetail = () => import('../views/CampaignDetail.vue');
const AccountPrep = () => import('../views/AccountPrep.vue');
const BotCreate = () => import('../views/BotCreate.vue');
const BotEdit = () => import('../views/BotEdit.vue');
const CampaignEdit = () => import('../views/CampaignEdit.vue');
const AppLayout = () => import('../layouts/AppLayout.vue');

const routes = [
  { path: '/', name: 'home', component: Home, meta: { title: 'Главная' } },
  { path: '/login', name: 'login', component: Login, meta: { guest: true, title: 'Вход' } },
  {
    path: '/app',
    component: AppLayout,
    meta: { requiresAuth: true },
    children: [
      { path: '', name: 'dashboard', component: Dashboard, meta: { title: 'Кампании' } },
      { path: 'campaigns/new', name: 'campaign-create', component: CampaignCreate, meta: { hideWorkflowNav: true, title: 'Новая кампания' } },
      { path: 'campaigns/:id', name: 'campaign-workspace', component: CampaignDetail, meta: { title: 'Кампания' } },
      {
        path: 'campaigns/:id/jobs',
        name: 'campaign-job-history',
        component: () => import('../views/CampaignJobHistory.vue'),
        meta: { hideWorkflowNav: true, title: 'История задач' },
      },
      {
        path: 'campaigns/:id/bots/bulk',
        name: 'bulk-bot-create',
        component: () => import('../views/BulkBotCreate.vue'),
        meta: { hideWorkflowNav: true, title: 'Массовое создание ботов' },
      },
      { path: 'campaigns/:id/bots/new', name: 'campaign-bot-create', component: BotCreate, meta: { hideWorkflowNav: true, title: 'Новый бот' } },
      { path: 'campaigns/:id/edit', name: 'campaign-edit', component: CampaignEdit, meta: { hideWorkflowNav: true, title: 'Редактирование кампании' } },
      { path: 'bots', redirect: { name: 'dashboard' } },
      {
        path: 'bots/new',
        redirect: () => ({ name: 'dashboard', query: { open: 'create_bot' } }),
      },
      { path: 'bots/:id/edit', name: 'bot-edit', component: BotEdit, meta: { hideWorkflowNav: true, title: 'Редактирование бота' } },
      { path: 'accounts/prepare', name: 'account-prep', component: AccountPrep, meta: { title: 'Подготовка аккаунтов' } },
      {
        path: 'settings',
        name: 'settings',
        component: () => import('../views/Settings.vue'),
        meta: { hideWorkflowNav: true, title: 'Настройки' },
      },
    ],
  },
  { path: '/:pathMatch(.*)*', redirect: '/' },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

router.beforeEach(async (to) => {
  const auth = useAuthStore();
  if (auth.user === null && localStorage.getItem('access_token')) {
    await auth.fetchUser();
  }

  if (to.meta.requiresAuth && !auth.isAuthenticated) {
    return { name: 'login', query: { redirect: to.fullPath } };
  }
  if (to.meta.guest && auth.isAuthenticated) {
    return { name: 'dashboard' };
  }
  return true;
});

router.afterEach((to) => {
  const pageTitle = to.meta.title;
  document.title = pageTitle ? `${pageTitle} — ${SITE_NAME}` : SITE_NAME;
});

export default router;
