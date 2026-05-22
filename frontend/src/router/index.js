import { createRouter, createWebHistory } from 'vue-router';
import { useAuthStore } from '../stores/authStore';

const Home = () => import('../views/Home.vue');
const Login = () => import('../views/Login.vue');
const Dashboard = () => import('../views/Dashboard.vue');
const CampaignCreate = () => import('../views/CampaignCreate.vue');
const CampaignDetail = () => import('../views/CampaignDetail.vue');
const AccountPrep = () => import('../views/AccountPrep.vue');
const BotsHub = () => import('../views/BotsHub.vue');
const BotCreate = () => import('../views/BotCreate.vue');
const BotEdit = () => import('../views/BotEdit.vue');
const CampaignEdit = () => import('../views/CampaignEdit.vue');
const AppLayout = () => import('../layouts/AppLayout.vue');

const routes = [
  { path: '/', name: 'home', component: Home },
  { path: '/login', name: 'login', component: Login, meta: { guest: true } },
  {
    path: '/app',
    component: AppLayout,
    meta: { requiresAuth: true },
    children: [
      { path: '', name: 'dashboard', component: Dashboard },
      { path: 'campaigns/new', name: 'campaign-create', component: CampaignCreate },
      { path: 'campaigns/:id', name: 'campaign-workspace', component: CampaignDetail },
      { path: 'campaigns/:id/bots/bulk', name: 'bulk-bot-create', component: () => import('../views/BulkBotCreate.vue') },
      { path: 'campaigns/:id/bots/new', name: 'campaign-bot-create', component: BotCreate },
      { path: 'campaigns/:id/edit', name: 'campaign-edit', component: CampaignEdit },
      { path: 'bots', name: 'bots-hub', component: BotsHub },
      { path: 'bots/new', name: 'bot-create', component: BotCreate },
      { path: 'bots/:id/edit', name: 'bot-edit', component: BotEdit },
      { path: 'accounts/prepare', name: 'account-prep', component: AccountPrep },
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

export default router;
