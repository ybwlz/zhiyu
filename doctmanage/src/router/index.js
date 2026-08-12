import { createRouter, createWebHistory } from 'vue-router'
import Admin from "@/views/Admin.vue";
import Docs from "@/views/Docs.vue";
import Login from "@/views/Login.vue";
import Home from "@/views/Home.vue";
import Changelog from "@/views/Changelog.vue";
import Activity from "@/views/Activity.vue";
import Guide from "@/views/Guide.vue";
import NotesSquare from "@/views/NotesSquare.vue";
import NoteReader from "@/views/NoteReader.vue";
import Profile from "@/views/Profile.vue";
import Friends from "@/views/Friends.vue";
import Messages from "@/views/Messages.vue";
import Mall from "@/views/Mall.vue";
import EditNote from "@/views/EditNote.vue";
import Settings from "@/views/Settings.vue";
import LegalPage from "@/views/LegalPage.vue";

const router = createRouter({
    history: createWebHistory(import.meta.env.BASE_URL),
    routes: [
        {
            path: '/',
            component: Home,
        },
        { path: '/docs', component: Docs },
        { path: '/docs/:key', component: Docs },
        { path: '/changelog', component: Changelog },
        { path: '/activity', component: Activity },
        { path: '/guide', component: Guide },
        { path: '/notes', component: NotesSquare },
        { path: '/notes/:key', component: NoteReader },
        { path: '/user/:key', component: Profile },
        { path: '/friends', component: Friends },
{ path: '/messages', component: Messages },
        { path: '/mall', component: Mall },
        { path: '/edit', component: EditNote },
        { path: '/settings', component: Settings },
        { path: '/edit/:id', component: EditNote },
        { path: '/technical-document', redirect: '/docs' },
        { path: '/technical-document/:slug', redirect: to => ({ path: `/docs/${to.params.slug}` }) },
        {
            path: '/admin',
            component: Admin,
        },
        { path: '/login', component: Login },
        { path: '/terms', component: LegalPage },
        { path: '/privacy', component: LegalPage },
        { path: '/:pathMatch(.*)*', component: () => import('@/views/NotFound.vue') },
    ],
    // 路由切换默认回到页面顶部；浏览器前进/后退时恢复原滚动位置
    scrollBehavior(to, from, savedPosition) {
        return savedPosition || { top: 0 }
    },
})

import { useAuthStore } from "@/stores/auth.js";

router.beforeEach((to, from, next) => {
    const auth = useAuthStore()
    // 需要登录的页面：编辑、后台、私信、好友、设置、商城
    const needsAuth = ['/admin', '/edit', '/messages', '/friends', '/settings', '/mall'].some(p => to.path.startsWith(p))
    if (needsAuth) {
        if (auth.isLogin) next()
        else next('/login')
    } else if (to.path === '/login' && auth.isLogin) {
        next('/admin')
    } else {
        next()
    }
})

export default router
