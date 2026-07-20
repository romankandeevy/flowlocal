// Раскладка страницы: «карточки» или «линии».
//
// В QML это `T.layout` - токен, а не настройка компонента, потому что сменить
// раскладку должно всё окно разом, как при смене темы. Здесь та же роль у
// контекста: Card спрашивает раскладку у него, а не получает пропсом. Пропс
// пришлось бы протаскивать через каждую страницу до каждой карточки, и первая
// же забытая осталась бы в коробке посреди списка.
//
// Умолчание - «карточки»: это канон Korti. «Линии» появились там, где рамок
// набиралось столько, что они спорили с содержимым (страница «Диктовка»).
import { createContext, useContext, type ReactNode } from "react";

export type LayoutMode = "cards" | "lines";

const Ctx = createContext<LayoutMode>("cards");

export function LayoutModeProvider({
  mode,
  children,
}: {
  mode: LayoutMode;
  children: ReactNode;
}) {
  return <Ctx.Provider value={mode}>{children}</Ctx.Provider>;
}

export function useLayoutMode(): LayoutMode {
  return useContext(Ctx);
}
