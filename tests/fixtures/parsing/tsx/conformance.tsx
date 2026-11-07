type Props = { name: string };
export const View = ({ name }: Props) => (
  <section aria-label={name}>
    <h1>{name.toUpperCase()}</h1>
    <button onClick={() => save(name)}>Save</button>
  </section>
);
